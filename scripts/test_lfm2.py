#!/usr/bin/env python3
"""Test LFM2-Audio-1.5B ASR on a voice message."""
import time
import torch
import torchaudio
from liquid_audio import LFM2AudioModel, LFM2AudioProcessor, ChatState

HF_REPO = "LiquidAI/LFM2-Audio-1.5B"

print("Loading processor...")
t0 = time.time()
processor = LFM2AudioProcessor.from_pretrained(HF_REPO, device="cpu").eval()
print(f"Processor loaded in {time.time()-t0:.1f}s")

print("Loading model...")
t0 = time.time()
model = LFM2AudioModel.from_pretrained(HF_REPO, device="cpu").eval()
print(f"Model loaded in {time.time()-t0:.1f}s")

# Load audio via soundfile
import subprocess
import soundfile as sf
import numpy as np
subprocess.run(["ffmpeg", "-y", "-i", "/home/dcarmitage/.clawdbot/media/inbound/1ca688bb-c8ae-48a9-9700-289b0ea73bb5.ogg", "-ar", "16000", "-ac", "1", "/tmp/lfm2_input.wav"], capture_output=True)
data, sr = sf.read("/tmp/lfm2_input.wav")
wav = torch.from_numpy(data.astype(np.float32)).unsqueeze(0)
print(f"Audio: {wav.shape}, sr={sr}")

# Set up ASR chat
chat = ChatState(processor)
chat.new_turn("system")
chat.add_text("Transcribe the following audio.")
chat.end_turn()

chat.new_turn("user")
chat.add_audio(wav, sr)
chat.end_turn()

chat.new_turn("assistant")

# Generate text only (sequential mode for ASR)
print("Transcribing...")
t0 = time.time()
text_out = []
for t in model.generate_sequential(**chat, max_new_tokens=256):
    if t.numel() == 1:
        decoded = processor.text.decode(t)
        print(decoded, end="", flush=True)
        text_out.append(decoded)

elapsed = time.time() - t0
print(f"\n\nTranscription took {elapsed:.1f}s")
