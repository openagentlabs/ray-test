import axios from 'axios';

const GEMINI_API_KEY = import.meta.env.VITE_GEMINI_API_KEY;
const GEMINI_API_URL = 'https://generativelanguage.googleapis.com/v1beta/models';

export type GeminiModel = 'gemini-2.5-flash-lite' | 'gemini-2.5-pro';

export async function geminiChatComplete({
  prompt,
  model = 'gemini-2.5-flash-lite',
  history = []
}: {
  prompt: string;
  model?: GeminiModel;
  history?: { role: 'user' | 'model'; parts: string[] }[];
}) {
  if (!GEMINI_API_KEY) {
    throw new Error('Gemini API key is not set. Please configure VITE_GEMINI_API_KEY in your .env');
  }
  const url = `${GEMINI_API_URL}/${model}:generateContent?key=${GEMINI_API_KEY}`;
  const messages = [
    ...history.map(h => ({ ...h, parts: h.parts.map(text => ({ text })) })),
    { role: 'user', parts: [{ text: prompt }] }
  ];
  try {
    const response = await axios.post(url, {
      contents: messages
    });
    // Gemini returns candidates[0].content.parts[0].text
    return response.data?.candidates?.[0]?.content?.parts?.[0]?.text || '';
  } catch (error: any) {
    return (
      error?.response?.data?.error?.message ||
      error?.message ||
      'Error contacting Gemini API.'
    );
  }
} 