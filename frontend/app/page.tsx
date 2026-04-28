"use client";

import { useEffect, useMemo, useRef, useState } from "react";

type ResumeResponse = {
  candidate_id: string;
  filename: string;
  chunks_indexed: number;
  extracted_summary: string;
  resume_highlights: string[];
};

type SessionResponse = {
  session_id: string;
  greeting: string;
  first_speaker: string;
};

type SessionSummary = {
  session_id: string;
  role: string;
  interview_mode: "strict" | "coaching";
  turn_count: number;
  active_agent: string;
  difficulty: string;
  status: "ready" | "live" | "completed" | "closed";
  latest_signal: string;
  focus_recommendation: string;
};

type Turn = {
  speaker: "candidate" | "agent";
  agent?: string;
  text: string;
};

type Report = {
  final_recommendation: string;
  scorecard: Record<string, number>;
  strengths: string[];
  weaknesses: string[];
  improvement_roadmap: string[];
};

type SpeechRecognitionCtor = new () => SpeechRecognition;

interface SpeechRecognitionEventLike extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEventLike extends Event {
  error: string;
}

interface SpeechRecognition extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionCtor;
    webkitSpeechRecognition?: SpeechRecognitionCtor;
  }
}

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "/api/v1";

const interviewerMeta: Record<string, { name: string; role: string }> = {
  hr: { name: "Maya", role: "HR Interviewer" },
  technical: { name: "Ethan", role: "Technical Interviewer" },
  hiring_manager: { name: "Jordan", role: "Hiring Manager" },
  feedback: { name: "Coach", role: "Live Feedback" },
};

const starterPrompts = [
  "I'd like to start with the experience on my resume that best matches this role.",
  "The project I most want to highlight from my resume is the one where I owned the core implementation.",
  "A resume example that shows both technical depth and impact is this one.",
];

const featureCards = [
  {
    title: "Resume-grounded questions",
    copy: "The interviewer uses your uploaded resume to pick projects, roles, and skills to probe instead of asking generic prompts.",
  },
  {
    title: "Natural voice loop",
    copy: "Turn on voice mode once, speak naturally, and let the conversation keep flowing after each interviewer response.",
  },
  {
    title: "Practical hiring signal",
    copy: "Every session ends with a focused scorecard and an improvement roadmap tied to your actual responses.",
  },
];

export default function HomePage() {
  const [resume, setResume] = useState<File | null>(null);
  const [resumeData, setResumeData] = useState<ResumeResponse | null>(null);
  const [role, setRole] = useState("Senior Machine Learning Engineer");
  const [mode, setMode] = useState<"strict" | "coaching">("coaching");
  const [domainFocus, setDomainFocus] = useState("ml,system-design,coding");
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [summary, setSummary] = useState<SessionSummary | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [candidateText, setCandidateText] = useState("");
  const [draftTranscript, setDraftTranscript] = useState("");
  const [report, setReport] = useState<Report | null>(null);
  const [status, setStatus] = useState("Your interview room is ready whenever you are.");
  const [wsReady, setWsReady] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isBrowserListening, setIsBrowserListening] = useState(false);
  const [voiceModeEnabled, setVoiceModeEnabled] = useState(false);
  const [isAgentSpeaking, setIsAgentSpeaking] = useState(false);
  const [isBusy, setIsBusy] = useState(false);

  const transcriptRef = useRef<HTMLDivElement | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const recognitionModeRef = useRef<"dictation" | "conversation">("dictation");
  const voiceBufferRef = useRef("");
  const shouldResumeVoiceRef = useRef(false);
  const voiceModeEnabledRef = useRef(false);
  const isAgentSpeakingRef = useRef(false);

  const recognitionSupported = useMemo(() => {
    if (typeof window === "undefined") {
      return false;
    }
    return Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  }, []);

  const latestAgent = [...turns].reverse().find((turn) => turn.speaker === "agent");
  const latestAgentMeta = latestAgent?.agent ? interviewerMeta[latestAgent.agent] : interviewerMeta.hr;
  const sessionReady = Boolean(resumeData);
  const interviewReady = Boolean(session && wsReady && summary?.status !== "closed");

  function resolveApiBase(): string {
    if (/^https?:\/\//.test(apiBase)) {
      return apiBase;
    }
    if (typeof window === "undefined") {
      return apiBase;
    }
    return new URL(apiBase, window.location.origin).toString();
  }

  function resolveWebSocketUrl(sessionId: string): string {
    if (typeof window !== "undefined") {
      const originProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsOrigin = `${originProtocol}//${window.location.host}`;
      return `${wsOrigin}/api/v1/ws/interview/${sessionId}`;
    }

    const wsBase = apiBase.replace("/api/v1", "");
    const wsProtocol = wsBase.startsWith("https://") ? "wss://" : "ws://";
    const wsHost = wsBase.replace(/^https?:\/\//, "");
    return `${wsProtocol}${wsHost}/api/v1/ws/interview/${sessionId}`;
  }

  useEffect(() => {
    transcriptRef.current?.scrollTo({ top: transcriptRef.current.scrollHeight, behavior: "smooth" });
  }, [turns, draftTranscript]);

  useEffect(() => {
    voiceModeEnabledRef.current = voiceModeEnabled;
  }, [voiceModeEnabled]);

  useEffect(() => {
    isAgentSpeakingRef.current = isAgentSpeaking;
  }, [isAgentSpeaking]);

  useEffect(() => {
    return () => {
      shouldResumeVoiceRef.current = false;
      recognitionRef.current?.stop();
      socketRef.current?.close();
      mediaRecorderRef.current?.stream?.getTracks().forEach((track) => track.stop());
      audioRef.current?.pause();
      if (typeof window !== "undefined") {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  async function uploadResume() {
    if (!resume) {
      setStatus("Choose a resume file first.");
      return;
    }

    setIsBusy(true);
    try {
      setStatus("Reading your resume so the interview can feel more personal.");
      const formData = new FormData();
      formData.append("file", resume);

      const response = await fetch(`${resolveApiBase()}/resume/upload`, {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        throw new Error(`Resume upload failed with status ${response.status}`);
      }

      const data: ResumeResponse = await response.json();
      setResumeData(data);
      setStatus(`Your resume is ready. I pulled in ${data.chunks_indexed} context section${data.chunks_indexed === 1 ? "" : "s"} for the interview.`);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Resume upload failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function startSession() {
    if (!resumeData) {
      setStatus("Upload your resume before starting a session.");
      return;
    }

    setIsBusy(true);
    try {
      setStatus("Setting up your interview room.");
      const response = await fetch(`${resolveApiBase()}/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate_id: resumeData.candidate_id,
          role,
          interview_mode: mode,
          domain_focus: domainFocus.split(",").map((item) => item.trim()).filter(Boolean),
        }),
      });

      if (!response.ok) {
        throw new Error(`Session creation failed with status ${response.status}`);
      }

      const data: SessionResponse = await response.json();
      setSession(data);
      setReport(null);
      setTurns([{ speaker: "agent", agent: data.first_speaker, text: data.greeting }]);
      setSummary({
        session_id: data.session_id,
        role,
        interview_mode: mode,
        turn_count: 0,
        active_agent: data.first_speaker,
        difficulty: "medium",
        status: "live",
        latest_signal: "mixed",
        focus_recommendation: "Answer with specific examples and measurable impact.",
      });
      speakAgentResponse(data.greeting);
      connectSocket(data.session_id);
    } catch (error) {
      setWsReady(false);
      setStatus(error instanceof Error ? error.message : "Session setup failed.");
    } finally {
      setIsBusy(false);
    }
  }

  function connectSocket(sessionId: string) {
    socketRef.current?.close();
    const ws = new WebSocket(resolveWebSocketUrl(sessionId));

    ws.onopen = () => {
      setWsReady(true);
      setStatus("Live interview started. You can type, dictate, or use voice mode.");
    };

    ws.onclose = () => {
      setWsReady(false);
      shouldResumeVoiceRef.current = false;
      stopBrowserListening();
      setIsRecording(false);
      setVoiceModeEnabled(false);
      setStatus((current) => (summary?.status === "closed" ? current : "Interview socket closed."));
    };

    ws.onerror = () => {
      setWsReady(false);
      setStatus("WebSocket connection failed. Make sure the backend is running.");
    };

    ws.onmessage = async (event) => {
      const message = JSON.parse(event.data);

      if (message.type === "agent_turn") {
        if (message.candidate_text) {
          setTurns((current) => {
            const lastTurn = current[current.length - 1];
            if (lastTurn?.speaker === "candidate" && lastTurn.text === message.candidate_text) {
              return current;
            }
            return [...current, { speaker: "candidate", text: message.candidate_text }];
          });
        }

        setTurns((current) => [...current, { speaker: "agent", agent: message.agent, text: message.text }]);
        setSummary((current) =>
          current
            ? {
                ...current,
                turn_count: current.turn_count + 1,
                active_agent: message.agent,
                latest_signal: message.latest_signal ?? current.latest_signal,
                focus_recommendation: message.focus_recommendation ?? current.focus_recommendation,
                status: message.should_end ? "completed" : current.status,
              }
            : current,
        );

        speakAgentResponse(message.text, message.audio_base64, Boolean(message.should_end));
        setStatus(message.should_end ? "Interview complete. Your report is ready." : "Interviewer responded.");
      }

      if (message.type === "final_report") {
        setReport(message.report);
      }

      if (message.type === "error") {
        setStatus(message.message ?? "Interview error.");
      }
    };

    socketRef.current = ws;
  }

  function sendCandidateText(textOverride?: string) {
    const outgoingText = (textOverride ?? candidateText).trim();
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN || !outgoingText) {
      setStatus("Start the interview and wait for the connection before sending an answer.");
      return;
    }

    stopBrowserListening();
    socketRef.current.send(JSON.stringify({ type: "candidate_text", text: outgoingText }));
    setTurns((current) => [...current, { speaker: "candidate", text: outgoingText }]);
    setCandidateText("");
    setDraftTranscript("");
    voiceBufferRef.current = "";
    setStatus("Answer sent. Your interviewer is thinking.");
  }

  async function resetSession() {
    if (!summary?.session_id) {
      setStatus("There is no active session to reset.");
      return;
    }

    setIsBusy(true);
    try {
      const response = await fetch(`${resolveApiBase()}/sessions/${summary.session_id}/reset`, { method: "POST" });
      if (!response.ok) {
        throw new Error(`Session reset failed with status ${response.status}`);
      }
      const nextSummary: SessionSummary = await response.json();
      shouldResumeVoiceRef.current = false;
      setVoiceModeEnabled(false);
      setSummary(nextSummary);
      setTurns([]);
      setReport(null);
      setCandidateText("");
      setDraftTranscript("");
      voiceBufferRef.current = "";
      stopBrowserListening();
      socketRef.current?.close();
      setSession((current) => (current ? { ...current, first_speaker: "hr", greeting: "" } : current));
      connectSocket(nextSummary.session_id);
      const greeting =
        "Hi, I'm Maya. We can start fresh. Introduce yourself the way you would at the beginning of a live interview.";
      setTurns([{ speaker: "agent", agent: "hr", text: greeting }]);
      speakAgentResponse(greeting);
      setStatus("Session reset. You're back at the start and ready to try again.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Session reset failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function endSession() {
    if (!summary?.session_id) {
      setStatus("There is no active session to close.");
      return;
    }

    setIsBusy(true);
    try {
      const response = await fetch(`${resolveApiBase()}/sessions/${summary.session_id}`, { method: "DELETE" });
      if (!response.ok) {
        throw new Error(`Session close failed with status ${response.status}`);
      }
      const closedSummary: SessionSummary = await response.json();
      shouldResumeVoiceRef.current = false;
      setVoiceModeEnabled(false);
      setSummary(closedSummary);
      socketRef.current?.close();
      setWsReady(false);
      stopBrowserListening();
      setIsRecording(false);
      setStatus("Interview ended. You can review it now or start fresh.");
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Session close failed.");
    } finally {
      setIsBusy(false);
    }
  }

  async function startVoiceRecording() {
    if (!session || !wsReady) {
      setStatus("Start the interview before recording.");
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });

      let mimeType = "audio/webm";
      if (!MediaRecorder.isTypeSupported(mimeType)) {
        mimeType = "audio/mp4";
        if (!MediaRecorder.isTypeSupported(mimeType)) {
          mimeType = "";
        }
      }

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : {});
      mediaRecorderRef.current = recorder;
      audioChunksRef.current = [];

      recorder.onstart = () => {
        setIsRecording(true);
        setStatus("Recording now. Take your time.");
      };

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      recorder.onstop = async () => {
        try {
          const blob = new Blob(audioChunksRef.current, { type: mimeType || "audio/webm" });
          const buffer = await blob.arrayBuffer();
          const bytes = new Uint8Array(buffer);
          let binary = "";
          bytes.forEach((byte) => {
            binary += String.fromCharCode(byte);
          });
          const base64 = btoa(binary);

          if (socketRef.current?.readyState === WebSocket.OPEN) {
            stopBrowserListening();
            socketRef.current.send(
              JSON.stringify({
                type: "candidate_audio",
                audio: base64,
                filename: mimeType === "audio/mp4" ? "candidate.mp4" : "candidate.webm",
              }),
            );
            setStatus("Got it. Processing your answer now.");
          } else {
            setStatus("Connection lost. Start a new interview session.");
          }
        } catch {
          setStatus("Audio processing failed. Please try again.");
        } finally {
          setIsRecording(false);
          stream.getTracks().forEach((track) => track.stop());
        }
      };

      recorder.onerror = () => {
        setStatus("Recording failed. Please try again.");
        setIsRecording(false);
        stream.getTracks().forEach((track) => track.stop());
      };

      recorder.start();
    } catch (error: unknown) {
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        setStatus("Microphone access was denied.");
      } else {
        setStatus("Microphone access failed.");
      }
      setIsRecording(false);
    }
  }

  function stopVoiceRecording() {
    mediaRecorderRef.current?.stop();
  }

  function startBrowserListening(mode: "dictation" | "conversation" = "dictation") {
    if (!recognitionSupported) {
      setStatus("Live browser dictation is not supported in this browser.");
      return;
    }
    if (!wsReady) {
      setStatus("Start the interview before using live dictation.");
      return;
    }

    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setStatus("Speech recognition is unavailable.");
      return;
    }

    recognitionRef.current?.stop();

    const recognition = new Recognition();
    recognition.lang = "en-US";
    recognition.continuous = mode === "dictation";
    recognition.interimResults = true;
    recognitionModeRef.current = mode;
    voiceBufferRef.current = "";

    recognition.onstart = () => {
      setIsBrowserListening(true);
      setStatus(mode === "conversation" ? "I'm listening. Go ahead when you're ready." : "Dictation is on.");
    };

    recognition.onresult = (event) => {
      let interim = "";
      let finalText = "";

      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        const transcript = result[0]?.transcript ?? "";
        if (result.isFinal) {
          finalText += `${transcript} `;
        } else {
          interim += transcript;
        }
      }

      if (finalText.trim()) {
        voiceBufferRef.current = `${voiceBufferRef.current} ${finalText}`.trim();
      }

      if (mode === "conversation") {
        setCandidateText(`${voiceBufferRef.current} ${interim}`.trim());
      } else if (finalText.trim()) {
        setCandidateText((current) => `${current} ${finalText}`.trim());
      }

      setDraftTranscript(interim.trim());
    };

    recognition.onerror = (event) => {
      setStatus(`Dictation error: ${event.error}`);
      setIsBrowserListening(false);
      recognitionRef.current = null;
      if (mode === "conversation") {
        shouldResumeVoiceRef.current = false;
        setVoiceModeEnabled(false);
      }
    };

    recognition.onend = () => {
      const transcript = voiceBufferRef.current.trim();
      const isConversation = recognitionModeRef.current === "conversation";
      const shouldResume = shouldResumeVoiceRef.current;

      recognitionRef.current = null;
      setIsBrowserListening(false);
      setDraftTranscript("");

      if (isConversation && transcript) {
        sendCandidateText(transcript);
        return;
      }

      if (isConversation && shouldResume && !isAgentSpeakingRef.current) {
        window.setTimeout(() => {
          if (shouldResumeVoiceRef.current && !recognitionRef.current && !isAgentSpeakingRef.current) {
            startBrowserListening("conversation");
          }
        }, 250);
      }
    };

    recognitionRef.current = recognition;
    recognition.start();
  }

  function stopBrowserListening() {
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    setIsBrowserListening(false);
    setDraftTranscript("");
    voiceBufferRef.current = "";
  }

  function setAgentSpeakingState(nextValue: boolean) {
    isAgentSpeakingRef.current = nextValue;
    setIsAgentSpeaking(nextValue);
  }

  function maybeResumeVoiceConversation(shouldEnd: boolean) {
    if (shouldEnd || !shouldResumeVoiceRef.current || !voiceModeEnabledRef.current) {
      return;
    }
    window.setTimeout(() => {
      if (shouldResumeVoiceRef.current && !recognitionRef.current && !isAgentSpeakingRef.current) {
        startBrowserListening("conversation");
      }
    }, 350);
  }

  function speakAgentResponse(text: string, audioBase64?: string, shouldEnd = false) {
    audioRef.current?.pause();
    audioRef.current = null;

    if (typeof window === "undefined" || !("speechSynthesis" in window)) {
      maybeResumeVoiceConversation(shouldEnd);
      return;
    }

    window.speechSynthesis.cancel();
    setAgentSpeakingState(true);

    if (audioBase64) {
      const audio = new Audio(`data:audio/wav;base64,${audioBase64}`);
      audioRef.current = audio;
      audio.onended = () => {
        setAgentSpeakingState(false);
        maybeResumeVoiceConversation(shouldEnd);
      };
      audio.onerror = () => {
        setAgentSpeakingState(false);
        speakAgentResponse(text, undefined, shouldEnd);
      };
      void audio.play().catch(() => {
        setAgentSpeakingState(false);
        speakAgentResponse(text, undefined, shouldEnd);
      });
      return;
    }

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1;
    utterance.pitch = 0.94;
    utterance.volume = 1;
    utterance.onend = () => {
      setAgentSpeakingState(false);
      maybeResumeVoiceConversation(shouldEnd);
    };
    utterance.onerror = () => {
      setAgentSpeakingState(false);
      maybeResumeVoiceConversation(shouldEnd);
    };
    window.speechSynthesis.speak(utterance);
  }

  function startVoiceMode() {
    if (!interviewReady) {
      setStatus("Start the interview before using voice mode.");
      return;
    }
    if (!recognitionSupported) {
      setStatus("Voice mode needs a browser with speech recognition support.");
      return;
    }

    shouldResumeVoiceRef.current = true;
    setVoiceModeEnabled(true);
    stopBrowserListening();
    startBrowserListening("conversation");
  }

  function stopVoiceMode() {
    shouldResumeVoiceRef.current = false;
    setVoiceModeEnabled(false);
    stopBrowserListening();
    setStatus("Voice mode stopped.");
  }

  return (
    <main className="page-shell">
      <section className="brand-hero">
        <div className="hero-content">
          <p className="eyebrow">Northstar Interview AI</p>
          <h1>Practice interviews that sound human, react intelligently, and push for real hiring signal.</h1>
          <p className="hero-text">
            Northstar combines resume context, live voice interaction, smarter follow-ups, and instant feedback so each
            interview feels tailored, responsive, and a lot closer to talking with a real person.
          </p>
          <div className="hero-actions">
            <button className="button primary inline-button" onClick={startSession} disabled={!sessionReady || isBusy}>
              Launch Interview
            </button>
            <span className="hero-subtle">Best in Chrome or Edge for microphone and speech recognition support.</span>
          </div>
        </div>

        <div className="hero-panel">
          <div className="signal-card">
            <p>Interviewer</p>
            <strong>{latestAgentMeta.name}</strong>
            <span>{latestAgentMeta.role}</span>
          </div>
          <div className="signal-card">
            <p>Status</p>
            <strong>{summary?.status ?? "standby"}</strong>
            <span>{status}</span>
          </div>
          <div className="signal-card">
            <p>Voice loop</p>
            <strong>{voiceModeEnabled ? (isAgentSpeaking ? "agent speaking" : isBrowserListening ? "listening" : "waiting") : "manual"}</strong>
            <span>
              {voiceModeEnabled
                ? "Hands-free mode will listen again after each interviewer response."
                : "Turn on voice mode for a more natural back-and-forth conversation."}
            </span>
          </div>
          <div className="signal-card">
            <p>Current signal</p>
            <strong>{summary?.latest_signal?.replaceAll("_", " ") ?? "waiting"}</strong>
            <span>{summary?.focus_recommendation ?? "Start a session to get live coaching cues."}</span>
          </div>
        </div>
      </section>

      <section className="feature-row">
        {featureCards.map((card) => (
          <article key={card.title} className="feature-card">
            <h2>{card.title}</h2>
            <p>{card.copy}</p>
          </article>
        ))}
      </section>

      <section className="workspace">
        <aside className="control-column">
          <div className="panel">
            <div className="panel-header">
              <h2>Session Setup</h2>
              <span>{resumeData ? "ready" : "waiting"}</span>
            </div>

            <div className="field">
              <label>Resume</label>
              <input type="file" accept=".pdf,.txt,.md" onChange={(event) => setResume(event.target.files?.[0] ?? null)} />
            </div>

            <button className="button secondary" onClick={uploadResume} disabled={isBusy}>
              Index Resume
            </button>

            <div className="field">
              <label>Role</label>
              <input value={role} onChange={(event) => setRole(event.target.value)} />
            </div>

            <div className="field">
              <label>Mode</label>
              <select value={mode} onChange={(event) => setMode(event.target.value as "strict" | "coaching")}>
                <option value="coaching">Coaching</option>
                <option value="strict">Strict</option>
              </select>
            </div>

            <div className="field">
              <label>Focus Areas</label>
              <input value={domainFocus} onChange={(event) => setDomainFocus(event.target.value)} />
            </div>

            <div className="button-grid">
              <button className="button primary" onClick={startSession} disabled={!sessionReady || isBusy}>
                Start Interview
              </button>
              <button className="button ghost" onClick={resetSession} disabled={!summary || isBusy}>
                Reset Session
              </button>
              <button className="button ghost" onClick={endSession} disabled={!summary || isBusy}>
                End Interview
              </button>
            </div>

            {resumeData && (
              <div className="resume-summary">
                <strong>{resumeData.filename}</strong>
                <p>{resumeData.extracted_summary}</p>
                {resumeData.resume_highlights.length > 0 && (
                  <ul className="report-list">
                    {resumeData.resume_highlights.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>

          <div className="panel">
            <div className="panel-header">
              <h2>Session Pulse</h2>
              <span>{summary?.difficulty ?? "medium"}</span>
            </div>

            <div className="pulse-grid">
              <div className="pulse-card">
                <span>Turns</span>
                <strong>{summary?.turn_count ?? 0}</strong>
              </div>
              <div className="pulse-card">
                <span>Mode</span>
                <strong>{summary?.interview_mode ?? mode}</strong>
              </div>
              <div className="pulse-card">
                <span>Round</span>
                <strong>{interviewerMeta[summary?.active_agent ?? "hr"]?.name ?? "Maya"}</strong>
              </div>
              <div className="pulse-card">
                <span>Signal</span>
                <strong>{summary?.latest_signal?.replaceAll("_", " ") ?? "waiting"}</strong>
              </div>
            </div>

            <p className="coach-note">{summary?.focus_recommendation ?? "Start the interview to see live coaching guidance."}</p>
          </div>

          <div className="panel">
            <div className="panel-header">
              <h2>Speak or Type</h2>
              <span>{interviewReady ? "connected" : "offline"}</span>
            </div>

            <div className="voice-mode-card">
              <div>
                <strong>Voice conversation mode</strong>
                <p>Start once, speak naturally, pause when you're done, and let the app respond before it listens again.</p>
              </div>
              <button
                className={`button ${voiceModeEnabled ? "ghost" : "primary"}`}
                onClick={voiceModeEnabled ? stopVoiceMode : startVoiceMode}
                disabled={!interviewReady || !recognitionSupported}
              >
                {voiceModeEnabled ? "Stop Voice Mode" : "Start Voice Mode"}
              </button>
            </div>

            <div className="quick-prompts">
              {starterPrompts.map((prompt) => (
                <button key={prompt} className="chip" onClick={() => setCandidateText(prompt)}>
                  {prompt}
                </button>
              ))}
            </div>

            <div className="field">
              <label>Your answer</label>
              <textarea
                rows={7}
                value={candidateText}
                onChange={(event) => setCandidateText(event.target.value)}
                placeholder="Answer naturally here, or use live dictation or voice mode."
              />
              {draftTranscript && <p className="draft-line">Listening: {draftTranscript}</p>}
            </div>

            <div className="button-grid">
              <button className="button primary" onClick={() => sendCandidateText()} disabled={!interviewReady}>
                Send Answer
              </button>
              <button
                className="button ghost"
                onClick={isRecording ? stopVoiceRecording : startVoiceRecording}
                disabled={!interviewReady}
              >
                {isRecording ? "Stop Recording" : "Record Audio"}
              </button>
              <button
                className="button ghost"
                onClick={isBrowserListening ? stopBrowserListening : () => startBrowserListening("dictation")}
                disabled={!interviewReady || !recognitionSupported}
              >
                {isBrowserListening ? "Stop Dictation" : "Live Dictation"}
              </button>
            </div>
          </div>
        </aside>

        <section className="conversation-column">
          <div className="panel interview-panel">
            <div className="panel-header">
              <h2>Interview Room</h2>
              <span>{turns.length} messages</span>
            </div>

            <div className="transcript" ref={transcriptRef}>
              {turns.length === 0 && (
                <div className="empty-state">
                  <strong>Your interviewer will appear here.</strong>
                  <p>Upload a resume and start the session to begin the conversation.</p>
                </div>
              )}

              {turns.map((turn, index) => {
                const meta = turn.agent ? interviewerMeta[turn.agent] : null;
                return (
                  <article
                    key={`${turn.speaker}-${index}`}
                    className={`turn ${turn.speaker === "candidate" ? "candidate" : `agent-${turn.agent}`}`}
                  >
                    <small>{turn.speaker === "candidate" ? "You" : `${meta?.name ?? turn.agent} | ${meta?.role ?? "Interviewer"}`}</small>
                    <div>{turn.text}</div>
                  </article>
                );
              })}
            </div>
          </div>

          {report && (
            <div className="report-grid">
              <div className="panel report-hero">
                <div className="panel-header">
                  <h2>Final Report</h2>
                  <span>{report.final_recommendation.replaceAll("_", " ")}</span>
                </div>
                <div className="score-strip">
                  {Object.entries(report.scorecard).map(([key, value]) => (
                    <div key={key} className="score-pill">
                      <span>{key.replaceAll("_", " ")}</span>
                      <strong>{value}</strong>
                    </div>
                  ))}
                </div>
              </div>

              <div className="panel">
                <h2>Strengths</h2>
                <ul className="report-list">
                  {report.strengths.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="panel">
                <h2>Needs Work</h2>
                <ul className="report-list">
                  {report.weaknesses.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              <div className="panel">
                <h2>Roadmap</h2>
                <ul className="report-list">
                  {report.improvement_roadmap.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </section>
      </section>
    </main>
  );
}
