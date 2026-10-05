# ViralClip AI v2 — Phone-first

This is a hosted web-app version. You do NOT install Python on your phone.

## What it does
- Upload one licensed VOD from Android.
- AI finds exactly 3 highlights.
- Generates original commentary scripts.
- Renders 9:16 vertical drafts with captions.
- Lets you upload your own voice commentary from the phone.
- Mixes your voice and provides final MP4 downloads.
- Stops before public YouTube posting so you can review.

## Easiest hosting
Use Streamlit Community Cloud:
1. Create a GitHub repository.
2. Upload `app.py`, `requirements.txt`, and `packages.txt`.
3. Deploy the repository as a Streamlit app.
4. In Streamlit app settings, add a secret:
   OPENAI_API_KEY = "your_key_here"
5. Open the app URL on your Android phone.

Never put your API key in the GitHub repository.

## Important
Only use video you have permission/license to use. Original commentary and editing can help make the content transformative, but do not assume that permission alone guarantees YouTube monetization.

## Models
The app uses OpenAI transcription and Responses API calls. Model names can be changed in `app.py` if your account has different model availability.


## Streamlit Cloud
Use `OPENAI_API_KEY = "your_key"` in Streamlit Cloud Advanced settings → Secrets. The app reads it with `st.secrets`.
