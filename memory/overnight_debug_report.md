# Overnight Debug Report — Raspberry Pi 5 Hardware Issues

**Date:** 2026-01-30  
**System:** Raspberry Pi 5 Model B Rev 1.1, Debian Trixie (13), Kernel 6.12.47+rpt-rpi-2712

---

## Issue 1: rpicam + Hailo "HailoRT not ready"

### Summary

The "HailoRT not ready!" message is **expected behavior** during `rpicam-still` capture — it is NOT a Hailo failure. The Hailo-8 NPU inference actually works correctly during the viewfinder/preview phase. A separate kernel driver bug (find_vma locking) was found and patched.

### Root Cause Analysis

**The "HailoRT not ready!" message is benign in the still capture context.**

The rpicam Hailo postprocessing pipeline requires three conditions to be met (`Ready()` method in `hailo_postprocessing_stage.hpp:160`):
```cpp
bool Ready() const { return init_ && low_res_stream_ && output_stream_; }
```

When `rpicam-still` operates, it goes through two phases:
1. **Viewfinder phase** (lores stream active) → Inference runs successfully
2. **Still capture phase** (lores stream torn down for full-res) → `low_res_stream_` becomes null → `Ready()` returns false → "HailoRT not ready!" printed

**Evidence that inference works correctly:**
- `rpicam-hello` with Hailo post-processing: ✅ No errors, runs for full duration
- `rpicam-vid` with Hailo post-processing: ✅ No errors, runs for full duration  
- `rpicam-still` viewfinder phase: ✅ No errors (streams include 640x640 BGR888 lores)
- `rpicam-still` capture phase: ❌ "HailoRT not ready!" (expected — no lores stream)

### Kernel Driver Bug Found & Fixed

The out-of-tree `hailo_pci` driver (v4.23.0, from `hailort-pcie-driver` package) had a **missing mmap_read_lock bug** in `hailo_vdma_buffer_map()`:

**File:** `/usr/src/hailort-pcie-driver/linux/vdma/memory.c` line 170  
**Bug:** `find_vma(current->mm, addr_or_fd)` called without holding `mmap_read_lock`  
**Kernel requirement:** Linux 6.12 requires `mmap_read_lock` before `find_vma()`  
**Symptom:** Kernel WARNING at `include/linux/rwsem.h:80` with call trace through `hailo_vdma_buffer_map`

**Fix applied:** Added `mmap_read_lock(current->mm)` / `mmap_read_unlock(current->mm)` around `find_vma()` call, matching the [upstream fix on GitHub](https://github.com/hailo-ai/hailort-drivers/blob/master/linux/vdma/memory.c).

```diff
     if (HAILO_DMA_DMABUF_BUFFER != buffer_type) {
+        mmap_read_lock(current->mm);
         vma = find_vma(current->mm, addr_or_fd);
+        mmap_read_unlock(current->mm);
```

**Driver rebuilt and installed:**
```bash
cd /usr/src/hailort-pcie-driver/linux/pcie && sudo make all
sudo xz -c hailo_pci.ko | sudo tee /lib/modules/$(uname -r)/kernel/drivers/misc/hailo_pci.ko.xz > /dev/null
sudo rmmod hailo_pci && sudo modprobe hailo_pci
sudo systemctl restart hailort.service
```

Backup of original: `/lib/modules/$(uname -r)/kernel/drivers/misc/hailo_pci.ko.xz.bak`  
Backup of source: `/usr/src/hailort-pcie-driver/linux/vdma/memory.c.bak`

### Additional Finding: Dual Driver Conflict

Two `hailo_pci.ko` modules exist:
| Path | Version | Type | Source |
|------|---------|------|--------|
| `kernel/drivers/misc/hailo_pci.ko.xz` | 4.23.0 | Out-of-tree (O) | `hailort-pcie-driver` package |
| `kernel/drivers/media/pci/hailo/hailo_pci.ko.xz` | 4.20.0 | In-tree | Kernel package |

The out-of-tree 4.23.0 driver loads by default (matching userspace `hailort` 4.23.0). The in-tree 4.20.0 driver is version-mismatched with the userspace library and should NOT be used.

### Remaining Issues

1. **Segfault on exit** of `rpicam-still` with Hailo post-processing — likely a cleanup/teardown race in the userspace library. No kernel crash. Low priority.
2. **`rpicam-still --zsl` + Hailo** is architecturally incompatible: ZSL mode doesn't maintain the lores stream needed for inference. This is a known design limitation, not a bug.

### Recommendations

1. **For still images with Hailo inference**: Use `rpicam-still` WITHOUT `--zsl` — inference runs during viewfinder phase and bounding boxes are drawn on the output image.
2. **For continuous inference**: Use `rpicam-vid` or `rpicam-hello` which maintain the lores stream throughout.
3. **Monitor for package updates**: When `hailort-pcie-driver` is updated past 4.23.0, the mmap_read_lock fix should be included upstream. Revert to the package version at that point.

---

## Issue 2: V4L2 H.264 Hardware Encoder Failing

### Summary

**The Raspberry Pi 5 does NOT have a hardware H.264 encoder.** This is a hardware limitation of the BCM2712 SoC, not a software or driver issue. There is no fix — only workarounds.

### Root Cause

The Pi 5's BCM2712 SoC removed the Broadcom VideoCore H.264 hardware encoder that was present on the Pi 4's BCM2711. The Pi 5 only has:
- **Hardware HEVC (H.265) decoder** — `rpi-hevc-dec` at `/dev/video19`
- **No hardware encoder** of any kind (no H.264, no HEVC encoding)

**Evidence:**
```
$ vcgencmd codec_enabled H264
H264=disabled

$ v4l2-ctl --list-devices
rpi-hevc-dec (platform:rpi-hevc-dec):
    /dev/video19        ← decoder only
```

While `ffmpeg` lists `h264_v4l2m2m` as available, this is a **generic wrapper** that requires an actual V4L2 M2M H.264 encoder device, which doesn't exist on the Pi 5. When ffmpeg tries to use it, it fails with `-22 (Invalid argument)` because there's no matching hardware device.

Similarly, `rpicam-vid` cannot find a hardware H.264 codec and reports "Unable to find an appropriate H.264 codec" when hardware encoding is specifically requested. However, **rpicam-vid does fall back to software `libx264` automatically** and works fine.

### Workarounds

1. **Use software H.264 encoding (libx264):**
   ```bash
   # rpicam-vid works out of the box (auto-falls back to libx264)
   rpicam-vid -o test.h264 --width 1920 --height 1080 -t 5000 -n
   
   # ffmpeg: explicitly use libx264
   ffmpeg -i input.mjpeg -c:v libx264 -preset fast output.mp4
   ```

2. **Use MJPEG encoding** (no hardware encoder needed):
   ```bash
   rpicam-vid -o test.mjpeg --codec mjpeg --width 1920 --height 1080 -t 5000 -n
   ```

3. **Software HEVC encoding** (if H.265 output is acceptable):
   ```bash
   ffmpeg -i input.mjpeg -c:v libx265 -preset fast output.mp4
   ```

4. **External hardware encoding**: Use a USB or PCIe video encoder card if hardware acceleration is critical.

### Performance Note

Software H.264 encoding via `libx264` on the Pi 5's Cortex-A76 cores is adequate for many use cases:
- 1080p @ ~25-30 FPS with `-preset fast`
- 720p @ ~60 FPS with `-preset ultrafast`

This is a significant step back from the Pi 4's dedicated hardware encoder but usable for most applications.

---

## System Information

| Component | Version |
|-----------|---------|
| Board | Raspberry Pi 5 Model B Rev 1.1 |
| OS | Debian GNU/Linux 13 (trixie) |
| Kernel | 6.12.47+rpt-rpi-2712 |
| Camera | imx708_wide (Pi Camera Module 3 Wide) |
| hailo-all | 5.1.1 |
| hailort | 4.23.0 |
| hailo-tappas-core | 5.1.0 |
| rpicam-apps | 1.11.0-1 |
| libcamera | 0.6.0+rpt20251202 |
| Hailo NPU | Hailo-8, 26 TOPS, FW 4.23.0 |

## Changes Made

1. **Patched** `/usr/src/hailort-pcie-driver/linux/vdma/memory.c` — added mmap_read_lock around find_vma
2. **Rebuilt** `hailo_pci.ko` out-of-tree driver module
3. **Installed** patched driver to `/lib/modules/$(uname -r)/kernel/drivers/misc/hailo_pci.ko.xz`
4. **Reloaded** hailo_pci module and restarted hailort.service

Backups stored at:
- `/lib/modules/6.12.47+rpt-rpi-2712/kernel/drivers/misc/hailo_pci.ko.xz.bak`
- `/usr/src/hailort-pcie-driver/linux/vdma/memory.c.bak`
