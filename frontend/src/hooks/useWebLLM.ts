import { CreateMLCEngine, InitProgressReport, MLCEngine } from "@mlc-ai/web-llm";
import { useCallback, useRef, useState } from 'react';

export interface Message {
    role: 'system' | 'user' | 'assistant';
    content: string;
}

export interface UseWebLLMReturn {
    messages: Message[];
    isLoading: boolean;
    isModelLoading: boolean;
    progress: string;
    progressVal: number;
    sendMessage: (content: string) => Promise<void>;
    loadModel: (modelId: string) => Promise<void>;
    resetChat: () => void;
    stop: () => void;
    error: string | null;
}

export const useWebLLM = (): UseWebLLMReturn => {
    const [messages, setMessages] = useState<Message[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [isModelLoading, setIsModelLoading] = useState(false);
    const [progress, setProgress] = useState('');
    const [progressVal, setProgressVal] = useState(0);
    const [error, setError] = useState<string | null>(null);
    const engine = useRef<MLCEngine | null>(null);

    const initProgressCallback = (report: InitProgressReport) => {
        setProgress(report.text);
        setProgressVal(report.progress);
    };

    const loadModel = useCallback(async (modelId: string) => {
        setIsModelLoading(true);
        setError(null);
        try {
            if (!engine.current) {
                engine.current = await CreateMLCEngine(modelId, {
                    initProgressCallback,
                });
            } else {
                await engine.current.reload(modelId);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to load model');
            console.error("Error loading model:", err);
        } finally {
            setIsModelLoading(false);
        }
    }, []);

    const sendMessage = useCallback(async (content: string) => {
        if (!engine.current) {
            setError("Engine not initialized. Please load a model first.");
            return;
        }

        const userMessage: Message = { role: 'user', content };
        setMessages((prev) => [...prev, userMessage]);
        setIsLoading(true);
        setError(null);

        try {
            const currentMessages = [...messages, userMessage];
            const chunks = await engine.current.chat.completions.create({
                messages: currentMessages,
                stream: true,
            });

            let assistantMessage = "";
            setMessages((prev) => [...prev, { role: 'assistant', content: '' }]);

            for await (const chunk of chunks) {
                const delta = chunk.choices[0]?.delta.content || "";
                assistantMessage += delta;
                setMessages((prev) => {
                    const newMessages = [...prev];
                    newMessages[newMessages.length - 1] = { role: 'assistant', content: assistantMessage };
                    return newMessages;
                });
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Failed to send message');
            console.error("Error sending message:", err);
        } finally {
            setIsLoading(false);
        }
    }, [messages]);

    const resetChat = useCallback(() => {
        setMessages([]);
        if (engine.current) {
            engine.current.resetChat();
        }
    }, []);

    const stop = useCallback(() => {
        if (engine.current) {
            engine.current.interruptGenerate();
            setIsLoading(false);
        }
    }, []);

    return {
        messages,
        isLoading,
        isModelLoading,
        progress,
        progressVal,
        sendMessage,
        loadModel,
        resetChat,
        stop,
        error,
    };
};
