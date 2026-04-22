"use client";

import { useEffect, useRef, useState } from "react";

declare global {
  interface Window {
    SpeechRecognition: typeof SpeechRecognition;
    webkitSpeechRecognition: typeof SpeechRecognition;
  }
}

type ResumeResponse = {
  candidate_id: string;
  filename: string;
  chunks_indexed: number;
  extracted_summary: string;
};

type SessionResponse = {
  session_id: string;
  greeting: string;
  first_speaker: string;
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

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000/api/v1";

export default function HomePage() {
  const [resume, setResume] = useState<File | null>(null);
  const [resumeData, setResumeData] = useState<ResumeResponse | null>(null);
  const [role, setRole] = useState("Senior Machine Learning Engineer");
  const [mode, setMode] = useState("coaching");
  const [domainFocus, setDomainFocus] = useState("ml,system-design,coding");
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [candidateText, setCandidateText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [status, setStatus] = useState("Idle");
  const socketRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    return () => socketRef.current?.close();
  }, []);

  async function uploadResume() {
    if (!resume) return;
    setStatus("Uploading resume and indexing FAISS context...");
    const formData = new FormData();
    formData.append("file", resume);

    const response = await fetch(`${apiBase}/resume/upload`, {
      method: "POST",
      body: formData
    });
    const data: ResumeResponse = await response.json();
    setResumeData(data);
    setStatus(`Indexed ${data.chunks_indexed} resume chunks for candidate ${data.candidate_id.slice(0, 8)}...`);
  }

  async function startSession() {
    if (!resumeData) return;
    setStatus("Creating interview session...");
    const response = await fetch(`${apiBase}/sessions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_id: resumeData.candidate_id,
        role,
        interview_mode: mode,
        domain_focus: domainFocus.split(",").map((item) => item.trim()).filter(Boolean)
      })
    });
    const data: SessionResponse = await response.json();
    setSession(data);
    setTurns([{ speaker: "agent", agent: data.first_speaker, text: data.greeting }]);
    setStatus("Session live. Connect voice or use transcript input.");

    const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/interview/${data.session_id}`);
    ws.onmessage = async (event) => {
      const message = JSON.parse(event.data);
      if (message.type === "agent_turn") {
        setTurns((current) => [...current, { speaker: "agent", agent: message.agent, text: message.text }]);
        if (message.audio_base64) {
          const audio = new Audio(`data:audio/mp3;base64,${message.audio_base64}`);
          void audio.play();
        }
      }
      if (message.type === "final_report") {
        setReport(message.report);
        setStatus("Interview finished. Final report generated.");
      }
    };
    socketRef.current = ws;
  }

  function sendCandidateText() {
    if (!socketRef.current || socketRef.current.readyState !== WebSocket.OPEN || !candidateText.trim()) return;
    socketRef.current.send(JSON.stringify({ type: "candidate_text", text: candidateText }));
    setTurns((current) => [...current, { speaker: "candidate", text: candidateText }]);
    setCandidateText("");
    setStatus("Awaiting planner and agent response...");
  }

  function startVoiceRecording() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
      alert('Speech recognition not supported in this browser.');
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setIsRecording(true);
      setStatus("Listening...");
    };

    recognition.onresult = (event) => {
      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        }
      }
      if (finalTranscript) {
        setCandidateText(prev => prev + finalTranscript);
      }
    };

    recognition.onerror = (event) => {
      console.error('Speech recognition error:', event.error);
      setIsRecording(false);
      setStatus("Voice input error. Try again.");
    };

    recognition.onend = () => {
      setIsRecording(false);
      setStatus("Voice input stopped.");
    };

    recognitionRef.current = recognition;
    recognition.start();
  }

  function stopVoiceRecording() {
    if (recognitionRef.current) {
      recognitionRef.current.stop();
    }
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <span>Multi-Agent GenAI + Agentic AI + Real-Time Voice</span>
        <h1>Voice-Based Autonomous Multi-Agent AI Interview Coach & Recruiter Simulator</h1>
        <p>
          Resume-aware interview simulation with LangGraph orchestration, planner-driven round switching, confidence
          scoring, adaptive difficulty, and speech-to-speech responses.
        </p>
      </section>

      <section className="grid">
        <div className="stack">
          <div className="panel">
            <h2>Session Setup</h2>
            <div className="stack">
              <div className="field">
                <label>Resume Upload</label>
                <input type="file" accept=".pdf,.txt,.md" onChange={(e) => setResume(e.target.files?.[0] ?? null)} />
              </div>
              <div className="button-row">
                <button className="button" onClick={uploadResume}>Index Resume</button>
              </div>
              <div className="field">
                <label>Target Role</label>
                <input value={role} onChange={(e) => setRole(e.target.value)} />
              </div>
              <div className="field">
                <label>Interview Mode</label>
                <select value={mode} onChange={(e) => setMode(e.target.value)}>
                  <option value="coaching">Coaching Mode</option>
                  <option value="strict">Strict Interview Mode</option>
                </select>
              </div>
              <div className="field">
                <label>Domain Focus</label>
                <input value={domainFocus} onChange={(e) => setDomainFocus(e.target.value)} />
              </div>
              <div className="button-row">
                <button className="button" onClick={startSession} disabled={!resumeData}>Start Interview</button>
              </div>
              <p>{status}</p>
            </div>
          </div>

          <div className="panel">
            <h2>Candidate Input</h2>
            <div className="stack">
              <div className="field">
                <label>Live transcript input</label>
                <textarea
                  rows={5}
                  value={candidateText}
                  onChange={(e) => setCandidateText(e.target.value)}
                  placeholder="Browser STT or Whisper transcript can be pushed here in real time."
                />
              </div>
              <div className="button-row">
                <button
                  className="button"
                  onClick={isRecording ? stopVoiceRecording : startVoiceRecording}
                  disabled={!session}
                >
                  {isRecording ? "Stop Voice Input" : "Start Voice Input"}
                </button>
                <button className="button" onClick={sendCandidateText} disabled={!session}>Send Answer</button>
              </div>
            </div>
          </div>
        </div>

        <div className="panel">
          <h2>Live Interview</h2>
          <div className="transcript">
            {turns.map((turn, index) => (
              <article
                key={`${turn.speaker}-${index}`}
                className={`turn ${turn.speaker === "candidate" ? "candidate" : `agent-${turn.agent}`}`}
              >
                <small>{turn.speaker === "candidate" ? "Candidate" : `Agent: ${turn.agent}`}</small>
                <div>{turn.text}</div>
              </article>
            ))}
          </div>

          {report && (
            <div className="report">
              <div className="report-card">
                <strong>Recommendation:</strong> {report.final_recommendation}
              </div>
              <div className="report-card">
                <strong>Scorecard:</strong> {Object.entries(report.scorecard).map(([key, value]) => `${key} ${value}`).join(" | ")}
              </div>
              <div className="report-card">
                <strong>Strengths:</strong> {report.strengths.join(" | ")}
              </div>
              <div className="report-card">
                <strong>Weaknesses:</strong> {report.weaknesses.join(" | ")}
              </div>
              <div className="report-card">
                <strong>Roadmap:</strong> {report.improvement_roadmap.join(" | ")}
              </div>
            </div>
          )}
        </div>
      </section>
    </main>
  );
}

