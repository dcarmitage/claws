import { execSync } from "child_process";

export default function (api: any) {
  // /snap — instant photo, no LLM
  api.registerCommand({
    name: "snap",
    description: "📸 Take a photo (instant, ~60ms)",
    acceptsArgs: false,
    requireAuth: true,
    handler: async (ctx: any) => {
      try {
        const filePath = execSync("curl -s http://localhost:5080/snap", {
          timeout: 5000,
        })
          .toString()
          .trim();

        if (filePath && filePath.startsWith("/")) {
          const d = new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" }));
          const day = String(d.getDate()).padStart(2, "0");
          const months = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"];
          const mon = months[d.getMonth()];
          const yr = String(d.getFullYear()).slice(-2);
          const hh = String(d.getHours()).padStart(2, "0");
          const mm = String(d.getMinutes()).padStart(2, "0");
          const ss = String(d.getSeconds()).padStart(2, "0");
          const now = `${day}${mon}${yr} · ${hh}:${mm}:${ss}`;
          return {
            text: `\`${now} · portal1\``,
            mediaUrl: `file://${filePath}`,
          };
        }
        return { text: "❌ Camera snap failed" };
      } catch (e: any) {
        return { text: `❌ Camera error: ${e.message}` };
      }
    },
  });

  // /clip — instant video recording
  api.registerCommand({
    name: "clip",
    description: "🎬 Record a video clip (default 5s)",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      try {
        const duration = parseInt(ctx.args) || 5;
        const cappedDuration = Math.min(Math.max(duration, 1), 60);

        const filePath = execSync(
          `curl -s "http://localhost:5080/clip?duration=${cappedDuration}"`,
          { timeout: (cappedDuration + 30) * 1000 }
        )
          .toString()
          .trim();

        if (filePath && filePath.startsWith("/")) {
          return {
            text: `🎬 ${cappedDuration}s clip`,
            mediaUrl: `file://${filePath}`,
          };
        }
        return { text: "❌ Clip capture failed" };
      } catch (e: any) {
        return { text: `❌ Clip error: ${e.message}` };
      }
    },
  });

  // /stream — start/stop live streaming
  api.registerCommand({
    name: "stream",
    description: "📡 Start/stop live stream (HLS or RTMP)",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      try {
        const args = (ctx.args || "").trim();

        if (args === "stop") {
          const res = execSync("curl -s http://localhost:5080/stream/stop", {
            timeout: 10000,
          }).toString();
          const data = JSON.parse(res);
          if (data.status === "not_running") return { text: "📡 No stream running." };
          if (data.recording) {
            // Wait for conversion (background thread in camservice)
            const mp4 = data.recording;
            for (let i = 0; i < 30; i++) {
              try {
                const stat = execSync(`stat -c %s "${mp4}" 2>/dev/null || echo 0`, {
                  timeout: 1000,
                }).toString().trim();
                if (parseInt(stat) > 0) break;
              } catch {}
              execSync("sleep 1");
            }
            return {
              text: `📡 Stream stopped · ${data.size_mb}MB`,
              mediaUrl: `file://${mp4}`,
            };
          }
          return { text: "📡 Stream stopped." };
        }

        if (args === "status" || args === "") {
          const res = execSync("curl -s http://localhost:5080/stream/status", {
            timeout: 5000,
          }).toString();
          const data = JSON.parse(res);
          if (!data.streaming) {
            return { text: "📡 Not streaming.\n`/stream start` — HLS on local network\n`/stream start rtmp://url` — push to YouTube/Twitch/X\n`/stream stop` — stop" };
          }
          return { text: `📡 Streaming (${data.mode})\nElapsed: ${data.elapsed}\n${data.hls_url ? `\`${data.hls_url}\`` : `RTMP: ${data.rtmp_url}`}` };
        }

        if (args.startsWith("start")) {
          const rest = args.replace(/^start\s*/, "").trim();
          // Parse options: "hud" flag and optional rtmp url
          const hasHud = /\bhud\b/i.test(rest);
          const rtmpUrl = rest.replace(/\bhud\b/gi, "").trim();
          
          let url = "http://localhost:5080/stream/start";
          const params: string[] = [];
          if (rtmpUrl) params.push(`rtmp=${encodeURIComponent(rtmpUrl)}`);
          if (hasHud) params.push("hud=1");
          if (params.length) url += "?" + params.join("&");
          
          const res = execSync(`curl -s "${url}"`, { timeout: 10000 }).toString();
          const data = JSON.parse(res);
          if (data.error) return { text: `❌ ${data.error}` };
          const hudLabel = hasHud ? " + HUD" : "";
          const info = data.hls_url
            ? `🖥 Watch: http://192.168.1.64:5080/stream/watch\n📺 VLC: \`http://192.168.1.64:5080/stream/live.m3u8\``
            : `Pushing to: ${data.rtmp_url}`;
          return { text: `📡 Stream started (${data.mode}${hudLabel})\n${info}\n\n\`/stream stop\` to end` };
        }

        return { text: "Usage: `/stream start [rtmp://url]` | `/stream stop` | `/stream status`" };
      } catch (e: any) {
        return { text: `❌ Stream error: ${e.message}` };
      }
    },
  });

  // /catalog — browse and search the media catalog
  api.registerCommand({
    name: "catalog",
    description: "📂 Browse and search the media catalog",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      try {
        const args = (ctx.args || "").trim();
        const py = "python3 /home/clawd/tools/catalog/catalog.py";

        if (!args || args === "stats") {
          const res = execSync(`${py} stats`, { timeout: 5000 }).toString().trim();
          const data = JSON.parse(res);

          const lines = [
            `📂 **Media Catalog**`,
            `${data.total_items} items · ${data.total_size_mb}MB · ${data.total_duration_mins}min`,
            "",
          ];

          // Devices
          for (const dev of (data.devices || [])) {
            const status = dev.online ? "🟢" : "🔴";
            const space = dev.total_gb ? `${dev.free_gb}GB free / ${dev.total_gb}GB` : "";
            lines.push(`${status} **${dev.label}** \`${dev.device_path}\``);
            lines.push(`   ${dev.items} items · ${dev.catalog_mb}MB · ${space}`);
          }

          lines.push("");
          for (const [type, count] of Object.entries(data.by_type)) {
            const emoji = { snap: "📸", clip: "🎬", stream: "📡", listen: "🎤", import: "📁" }[type as string] || "📄";
            lines.push(`${emoji} ${type}: ${count}`);
          }
          return { text: lines.join("\n") };
        }

        if (args === "recent" || args.startsWith("recent")) {
          const n = parseInt(args.split(" ")[1]) || 10;
          const res = execSync(`${py} recent ${n}`, { timeout: 5000 }).toString().trim();
          if (!res) return { text: "📂 Catalog is empty." };
          return { text: `📂 **Recent (${n})**\n\`\`\`\n${res}\n\`\`\`` };
        }

        if (args.startsWith("search ")) {
          const query = args.slice(7).trim();
          const res = execSync(`${py} search ${query}`, { timeout: 5000 }).toString().trim();
          if (!res) return { text: `📂 No results for "${query}"` };
          return { text: `📂 **Search: ${query}**\n\`\`\`\n${res}\n\`\`\`` };
        }

        if (args === "handshake" || args === "scan") {
          const res = execSync(`${py} handshake`, { timeout: 15000 }).toString().trim();
          const data = JSON.parse(res);
          return { text: data.message };
        }

        if (args.startsWith("transfer")) {
          const parts = args.split(" ");
          if (parts.length < 3) {
            // Smart default: SD → first online USB
            const statsRes = execSync(`${py} stats`, { timeout: 5000 }).toString().trim();
            const stats = JSON.parse(statsRes);
            const sd = (stats.devices || []).find((d: any) => d.id === "sd:mmcblk0p2");
            const usb = (stats.devices || []).find((d: any) => d.id !== "sd:mmcblk0p2" && d.online);
            if (!usb) return { text: "❌ No external drive online to transfer to." };
            if (!sd || sd.items === 0) return { text: "📂 Nothing on SD card to transfer." };
            const res = execSync(`${py} transfer sd:mmcblk0p2 ${usb.id}`, { timeout: 120000 }).toString().trim();
            const data = JSON.parse(res);
            return { text: data.message };
          }
          const res = execSync(`${py} transfer ${parts[1]} ${parts[2]}`, { timeout: 120000 }).toString().trim();
          const data = JSON.parse(res);
          return { text: data.message };
        }

        if (args === "devices") {
          const res = execSync(`${py} devices`, { timeout: 5000 }).toString().trim();
          return { text: `📂 **Devices**\n\`\`\`\n${res}\n\`\`\`` };
        }

        return { text: "Usage:\n`/catalog` — stats + devices\n`/catalog recent [n]` — recent items\n`/catalog search <query>` — full-text search\n`/catalog handshake` — detect + register drives\n`/catalog transfer` — move media SD→USB\n`/catalog devices` — list all drives" };
      } catch (e: any) {
        return { text: `❌ Catalog error: ${e.message}` };
      }
    },
  });

  // /listen — record audio + transcribe
  api.registerCommand({
    name: "listen",
    description: "🎤 Record audio and transcribe (default 5s)",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      try {
        const duration = parseInt(ctx.args) || 5;
        const cappedDuration = Math.min(Math.max(duration, 1), 30);
        const ts = new Date().toISOString().replace(/[:.]/g, "-");
        const wavPath = `/home/clawd/media/listen_${ts}.wav`;

        // Record
        execSync(
          `arecord -D hw:0,0 -f S16_LE -r 16000 -c 1 -d ${cappedDuration} ${wavPath}`,
          { timeout: (cappedDuration + 5) * 1000 }
        );

        // Transcribe
        const transcript = execSync(
          `curl -s -X POST http://localhost:5092/v1/audio/transcriptions -F "file=@${wavPath}" -F "response_format=text"`,
          { timeout: 60000 }
        )
          .toString()
          .trim();

        if (transcript) {
          return { text: `🎤 *${transcript}*` };
        }
        return { text: "🎤 _(no speech detected)_" };
      } catch (e: any) {
        return { text: `❌ Listen error: ${e.message}` };
      }
    },
  });
}
