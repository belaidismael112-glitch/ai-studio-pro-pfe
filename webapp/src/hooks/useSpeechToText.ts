"use client";

import { useEffect, useRef, useState } from "react";

interface UseSpeechToTextOptions {
  lang?: string;
  continuous?: boolean;
  interimResults?: boolean;
}

export function useSpeechToText({
  lang = "fr-FR",
  continuous = false,
  interimResults = true,
}: UseSpeechToTextOptions = {}) {
  const recognitionRef = useRef<any>(null);
  const [supported, setSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [finalTranscript, setFinalTranscript] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setSupported(false);
      return;
    }
    setSupported(true);
    const recognition = new SpeechRecognition();
    recognition.lang = lang;
    recognition.continuous = continuous;
    recognition.interimResults = interimResults;
    recognition.onstart = () => {
      setListening(true);
      setError("");
    };
    recognition.onend = () => setListening(false);
    recognition.onerror = (event: any) => {
      setError(event?.error || "Speech recognition error");
      setListening(false);
    };
    recognition.onresult = (event: any) => {
      let interimText = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalText += text + " ";
        else interimText += text;
      }
      if (finalText) setFinalTranscript((prev) => `${prev} ${finalText}`.trim());
      setTranscript(interimText);
    };
    recognitionRef.current = recognition;
    return () => {
      try { recognition.stop(); } catch {}
    };
  }, [lang, continuous, interimResults]);

  const startListening = () => {
    if (!recognitionRef.current) return;
    setTranscript("");
    setFinalTranscript("");
    setError("");
    recognitionRef.current.lang = lang;
    recognitionRef.current.start();
  };

  const stopListening = () => recognitionRef.current?.stop();

  const resetTranscript = () => {
    setTranscript("");
    setFinalTranscript("");
    setError("");
  };

  return { supported, listening, transcript, finalTranscript, error, startListening, stopListening, resetTranscript };
}
