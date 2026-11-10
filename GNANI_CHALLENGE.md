# Jarvis — Gnani AI Challenge Build

Jarvis is now an Indian-language, voice-authenticated desktop assistant:

1. `Hey Jarvis` stays entirely local with openWakeWord.
2. The command recording is captured once as 16 kHz mono WAV.
3. Gnani **Prisma v2.5** transcribes it, including Indic languages and code-mixed speech.
4. When enabled, Gnani **Inya Shield / armour365** verifies the same recording before Jarvis runs any command.
5. Gnani **Timbre** speaks the reply with an Indic voice.

## Configure

Copy the Gnani entries from `.env.example` into `.env` and set `GNANI_API_KEY`.
`GNANI_LANGUAGE_CODE` can be `hi-IN`, `en-IN`, `ta-IN`, and other Prisma-supported language codes.

To turn on speaker verification, obtain the Armour365/Inya Shield credentials and set:

```env
GNANI_BIOMETRICS_ENABLED=true
GNANI_BIOMETRIC_TOKEN=...
GNANI_BIOMETRIC_ACCESS_KEY=...
GNANI_BIOMETRIC_USER_ID=you@example.com
GNANI_BIOMETRIC_SPEAKER=your-consented-speaker-id
```

Enroll from Jarvis's authenticated local remote API. This records eight seconds from the microphone attached to the Jarvis computer, sends it over TLS to Gnani, then deletes the temporary WAV:

```powershell
Invoke-RestMethod -Method Post `
  -Headers @{ Authorization = "Bearer <remote-token>" } `
  http://localhost:8765/api/biometrics/enroll
```

Enrollment requires the speaker's clear, affirmative consent. The application does not retain raw enrollment or verification audio; Armour365 retains the encrypted voiceprint.

## Demo outline

1. Show the local wake word working offline.
2. Enroll a consenting demo speaker through the protected endpoint.
3. Say a Hinglish/Indic command and show Prisma's transcript, successful verification, and Timbre reply.
4. Use a second consenting speaker or a recorded replay (only if allowed by your test environment) to show command access is denied.
5. State clearly that Gnani Prisma, Timbre, and Inya Shield/armour365 power the flow, and that all demo voice data is consented/synthetic.

For the Great Indian AI Internship Challenge, publish the working demo with
`#GnaniAI` and `#GreatIndianAIInternshipChallenge` before submitting.
