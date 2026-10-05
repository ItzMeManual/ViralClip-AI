
import os, json, subprocess, tempfile, shutil
from pathlib import Path
import streamlit as st
from openai import OpenAI

APP = Path(__file__).parent
WORK = APP / "jobs"
WORK.mkdir(exist_ok=True)

st.set_page_config(page_title="ViralClip AI", page_icon="🎬", layout="centered")

# Mobile-friendly styling
st.markdown("""
<style>
.block-container {max-width: 760px; padding-top: 1rem; padding-bottom: 4rem;}
.stButton button {width:100%; min-height:48px; border-radius:14px; font-size:1.05rem;}
.stDownloadButton button {width:100%; min-height:48px; border-radius:14px;}
</style>
""", unsafe_allow_html=True)

st.title("🎬 ViralClip AI")
st.caption("Version 2 • Phone-first clip maker")

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["OPENAI_API_KEY"]
    except Exception:
        api_key = None
if not api_key:
    with st.expander("🔐 One-time setup"):
        api_key = st.text_input("OpenAI API key", type="password")
        st.caption("For a hosted version, put the key in Streamlit Secrets instead of sharing it.")
if not api_key:
    st.info("Add your OpenAI API key to start.")
    st.stop()

client = OpenAI(api_key=api_key)

def run(cmd):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if p.returncode:
        raise RuntimeError(p.stderr[-4000:])
    return p

def safe_name(name):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in name)

def transcribe(video):
    audio = WORK / "audio.mp3"
    run(["ffmpeg","-y","-i",str(video),"-vn","-ac","1","-ar","16000","-b:a","64k",str(audio)])
    with open(audio, "rb") as f:
        tr = client.audio.transcriptions.create(
            model="gpt-4o-transcribe",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )
    segs = getattr(tr, "segments", None) or []
    return [{"start": float(s.start), "end": float(s.end), "text": s.text.strip()} for s in segs]

def find_highlights(segs):
    transcript = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segs)
    prompt = f"""
You are the highlight editor for ViralClip AI.

Select EXACTLY 3 distinct moments from this licensed livestream transcript.
Choose moments that can work as short-form videos: surprising reactions, funny moments,
high-energy gameplay, emotional moments, arguments, or a clear payoff.

Rules:
- Each clip should be 20-55 seconds.
- Do not invent events.
- start_sec and end_sec MUST correspond to the transcript timestamps.
- Include 2-5 seconds of context before the key moment where possible.
- Write ORIGINAL commentary that adds context/analysis/reaction; do not merely repeat the streamer.
- Give a short hook and a YouTube Shorts title.
- Return JSON only.

Schema:
{{
  "clips": [
    {{
      "start_sec": 0,
      "end_sec": 30,
      "hook": "...",
      "reason": "...",
      "commentary_script": "...",
      "title": "..."
    }}
  ]
}}

Transcript:
{transcript}
"""
    r = client.responses.create(model="gpt-6-luna", input=prompt)
    return json.loads(r.output_text)["clips"]

def make_srt(segs, start, end, path):
    rows = []
    for s in segs:
        a, b = max(s["start"], start), min(s["end"], end)
        if b > a:
            rows.append((a-start, b-start, s["text"]))
    def ts(x):
        ms = int(round((x-int(x))*1000))
        total = int(x); sec = total % 60; mins = (total//60) % 60; hrs = total//3600
        return f"{hrs:02d}:{mins:02d}:{sec:02d},{ms:03d}"
    with open(path, "w", encoding="utf-8") as f:
        for i,(a,b,t) in enumerate(rows,1):
            f.write(f"{i}\n{ts(a)} --> {ts(b)}\n{t}\n\n")

def render_vertical(src, start, end, srt, out):
    # Center-fit foreground over blurred vertical background.
    vf = (
        "split=2[bg][fg];"
        "[bg]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,boxblur=18:2[bg2];"
        "[fg]scale=1080:1920:force_original_aspect_ratio=decrease[fg2];"
        "[bg2][fg2]overlay=(W-w)/2:(H-h)/2"
    )
    if srt:
        vf += ",subtitles=" + str(srt).replace("\\","/").replace(":","\\:")
    run(["ffmpeg","-y","-ss",str(start),"-t",str(max(5,end-start)),
         "-i",str(src),"-vf",vf,"-c:v","libx264","-preset","veryfast",
         "-crf","23","-c:a","aac","-b:a","128k",str(out)])

def mix_voice(video, voice, out):
    # Voice is mixed with original audio. Original audio stays audible.
    run(["ffmpeg","-y","-i",str(video),"-i",str(voice),
         "-filter_complex",
         "[0:a]volume=0.55[orig];[1:a]volume=1.25[voice];"
         "[orig][voice]amix=inputs=2:duration=first:dropout_transition=2[a]",
         "-map","0:v","-map","[a]","-c:v","copy","-c:a","aac","-b:a","128k",str(out)])

if "job" not in st.session_state:
    st.session_state.job = None

uploaded = st.file_uploader(
    "1️⃣ Upload ONE licensed video",
    type=["mp4","mov","mkv","webm"],
    help="Only upload footage you have permission/license to use."
)

if uploaded:
    job = WORK / safe_name(Path(uploaded.name).stem)
    job.mkdir(exist_ok=True)
    source = job / safe_name(uploaded.name)
    if not source.exists():
        source.write_bytes(uploaded.getbuffer())
    st.success("Video received.")

    if st.button("🚀 Find my 3 best moments"):
        with st.spinner("AI is listening to the video and finding the strongest moments…"):
            try:
                segs = transcribe(source)
                clips = find_highlights(segs)
                (job/"segments.json").write_text(json.dumps(segs), encoding="utf-8")
                (job/"clips.json").write_text(json.dumps(clips, indent=2), encoding="utf-8")
                st.session_state.job = str(job)
                st.success("Found 3 clips!")
            except Exception as e:
                st.error(f"Could not process the video: {e}")

job = Path(st.session_state.job) if st.session_state.job else None
if job and (job/"clips.json").exists():
    clips = json.loads((job/"clips.json").read_text())
    segs = json.loads((job/"segments.json").read_text())

    st.divider()
    st.subheader("2️⃣ Your 3 Shorts")

    for i, c in enumerate(clips[:3], 1):
        st.markdown(f"### Short {i}: {c['title']}")
        st.write(f"**Hook:** {c['hook']}")
        st.write(f"**Why:** {c['reason']}")
        st.write("**Your commentary script:**")
        st.info(c["commentary_script"])

        srt = job/f"clip{i}.srt"
        vertical = job/f"Short_{i}_vertical.mp4"
        final = job/f"Short_{i}_FINAL.mp4"

        if st.button(f"🎞️ Create vertical Short {i}", key=f"render{i}"):
            make_srt(segs, float(c["start_sec"]), float(c["end_sec"]), srt)
            with st.spinner("Rendering…"):
                render_vertical(job/safe_name(next(p.name for p in job.iterdir() if p.suffix.lower() in [".mp4",".mov",".mkv",".webm"])),
                                float(c["start_sec"]), float(c["end_sec"]), srt, vertical)
            st.session_state[f"ready{i}"] = True

        if vertical.exists():
            st.video(str(vertical))
            st.download_button("⬇️ Save draft to phone", vertical.read_bytes(),
                               file_name=vertical.name, mime="video/mp4", key=f"draft{i}")

            voice = st.file_uploader(
                f"🎙️ Upload your voice commentary for Short {i}",
                type=["mp3","m4a","wav","aac"], key=f"voice{i}"
            )
            if voice:
                vp = job/f"voice{i}{Path(voice.name).suffix}"
                vp.write_bytes(voice.getbuffer())
                if st.button(f"🎧 Mix my commentary — Short {i}", key=f"mix{i}"):
                    with st.spinner("Mixing your voice…"):
                        mix_voice(vertical, vp, final)
                    st.success("Final Short ready for review.")
            if final.exists():
                st.video(str(final))
                st.download_button("📥 Download FINAL Short", final.read_bytes(),
                                   file_name=final.name, mime="video/mp4", key=f"final{i}")
                st.caption(f"Suggested YouTube title: {c['title']}")
                st.caption("Review the final video on your phone before publishing.")

    st.divider()
    st.subheader("✅ 3️⃣ Phone review")
    st.write("Check all three videos. Reject anything that is inaccurate, weak, or not properly licensed. Then upload the approved files through YouTube Studio.")
