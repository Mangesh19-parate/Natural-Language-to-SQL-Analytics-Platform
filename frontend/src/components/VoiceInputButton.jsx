import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, AlertCircle } from 'lucide-react';

/**
 * VoiceInputButton (Task T-43 / REQ-VOICE-01 / Week 14 P2)
 * Integrates Web Speech API (webkitSpeechRecognition / SpeechRecognition)
 * for natural voice capture directly into the Intent Studio input box.
 */
export default function VoiceInputButton({ onTranscript, disabled = false }) {
  const [isListening, setIsListening] = useState(false);
  const [isSupported, setIsSupported] = useState(true);
  const [errorMessage, setErrorMessage] = useState(null);
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setIsSupported(false);
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setIsListening(true);
      setErrorMessage(null);
    };

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0].transcript)
        .join('');

      if (onTranscript) {
        onTranscript(transcript, event.results[0].isFinal);
      }
    };

    recognition.onerror = (event) => {
      console.warn('Speech recognition error:', event.error);
      setIsListening(false);
      if (event.error === 'not-allowed') {
        setErrorMessage('Microphone access denied');
      } else if (event.error !== 'no-speech') {
        setErrorMessage(`Voice error: ${event.error}`);
      }
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore
        }
      }
    };
  }, [onTranscript]);

  const toggleListening = () => {
    if (!isSupported) {
      alert('Speech Recognition is not supported by your browser. Please use Chrome/Edge or modern browser.');
      return;
    }

    if (isListening) {
      try {
        recognitionRef.current?.stop();
      } catch (err) {
        console.error(err);
      }
    } else {
      setErrorMessage(null);
      try {
        recognitionRef.current?.start();
      } catch (err) {
        console.error('Failed to start recognition:', err);
      }
    }
  };

  if (!isSupported) {
    return (
      <button
        type="button"
        disabled
        title="Speech recognition not supported in this browser"
        className="p-2.5 rounded-xl bg-slate-800/40 text-slate-500 border border-slate-700/50 cursor-not-allowed opacity-60"
        aria-label="Voice input unsupported"
      >
        <MicOff className="w-5 h-5" />
      </button>
    );
  }

  return (
    <div className="relative inline-flex items-center">
      <button
        type="button"
        onClick={toggleListening}
        disabled={disabled}
        aria-label={isListening ? 'Stop voice listening' : 'Start voice input (Task T-43)'}
        title={isListening ? 'Listening... click to stop' : 'Click to speak query (Voice Capture)'}
        className={`p-2.5 rounded-xl border transition-all duration-300 flex items-center justify-center relative ${
          isListening
            ? 'bg-rose-600/30 text-rose-400 border-rose-500 shadow-lg shadow-rose-500/20 ring-2 ring-rose-500/40 animate-pulse'
            : 'bg-slate-800/80 hover:bg-slate-700 text-slate-300 border-slate-700 hover:text-white hover:border-slate-600'
        } ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}
      >
        {isListening ? (
          <>
            <Mic className="w-5 h-5 animate-bounce text-rose-400" />
            <span className="absolute -top-1 -right-1 flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-500"></span>
            </span>
          </>
        ) : (
          <Mic className="w-5 h-5" />
        )}
      </button>

      {errorMessage && (
        <div className="absolute bottom-full mb-2 left-1/2 -translate-x-1/2 px-2.5 py-1 rounded-lg bg-rose-950 border border-rose-800 text-[11px] text-rose-300 whitespace-nowrap shadow-lg flex items-center gap-1 z-50">
          <AlertCircle className="w-3 h-3 text-rose-400" />
          <span>{errorMessage}</span>
        </div>
      )}
    </div>
  );
}
