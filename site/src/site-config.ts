import type { SiteConfig } from '@mcptoolshop/site-theme';

export const config: SiteConfig = {
  title: 'Voice Soundboard',
  description: 'Text-to-speech for AI agents and developers. Compiler → Graph → Engine architecture.',
  logoBadge: 'VS',
  brandName: 'Voice Soundboard',
  repoUrl: 'https://github.com/mcp-tool-shop-org/voice-soundboard',
  footerText: 'MIT Licensed — built by <a href="https://github.com/mcp-tool-shop-org" style="color:var(--color-muted);text-decoration:underline">mcp-tool-shop-org</a>',

  hero: {
    badge: 'Open source',
    headline: 'Voice Soundboard',
    headlineAccent: 'TTS for AI agents.',
    description: 'A text-to-speech engine that separates what is said from how it\u2019s rendered. Compiler \u2192 Graph \u2192 Engine architecture with swappable backends.',
    primaryCta: { href: '#usage', label: 'Get started' },
    secondaryCta: { href: '#architecture', label: 'How it works' },
    previews: [
      { label: 'Install', code: 'pip install voice-soundboard' },
      { label: 'Speak', code: "engine.speak('Hello world!')" },
      { label: 'Emotion', code: "engine.speak('Great news!', emotion='excited')" },
    ],
  },

  sections: [
    {
      kind: 'features',
      id: 'features',
      title: 'Features',
      subtitle: 'Everything you need for production TTS.',
      features: [
        { title: 'Compiler / Graph / Engine', desc: 'Intent compiles to a ControlGraph. The engine renders it to audio. Features are free at runtime.' },
        { title: 'Swappable Backends', desc: 'Kokoro (GPU), Piper (CPU), OpenAI, ElevenLabs, Azure — switch without changing code.' },
        { title: 'Emotions & Styles', desc: 'Add emotion="happy" or style="warmly and cheerfully" — the compiler bakes it into the graph.' },
        { title: 'Streaming Synthesis', desc: 'Sentence-level streaming for LLM output. compile_stream() yields graphs as text arrives.' },
        { title: 'CLI Included', desc: 'voice-soundboard speak "Hello!" — with presets, voice selection, and speed control.' },
        { title: 'MCP Server Ready', desc: 'Built-in MCP adapter so AI agents can synthesize speech through the standard tool protocol.' },
      ],
    },
    {
      kind: 'code-cards',
      id: 'usage',
      title: 'Usage',
      cards: [
        {
          title: 'Install',
          code: '# Core library\npip install voice-soundboard\n\n# With Kokoro backend (GPU)\npip install voice-soundboard[kokoro]\n\n# With Piper backend (CPU)\npip install voice-soundboard[piper]',
        },
        {
          title: 'Basic',
          code: "from voice_soundboard import VoiceEngine\n\nengine = VoiceEngine()\nresult = engine.speak('Hello world!')\nprint(f'Saved to: {result.audio_path}')",
        },
        {
          title: 'With voice & emotion',
          code: "result = engine.speak(\n    'Breaking news!',\n    voice='bm_george',\n    preset='announcer',\n    emotion='excited'\n)",
        },
        {
          title: 'Streaming (LLM output)',
          code: "from voice_soundboard.compiler import compile_stream\nfrom voice_soundboard.runtime import StreamingSynthesizer\n\nfor graph in compile_stream(llm_chunks()):\n    for chunk in streamer.stream(graph):\n        play(chunk)",
        },
      ],
    },
    {
      kind: 'features',
      id: 'architecture',
      title: 'Architecture',
      subtitle: 'Compiler \u2192 Graph \u2192 Engine. Clean separation, zero-cost features.',
      features: [
        { title: 'Compiler', desc: 'Transforms text + emotion + style into a pure-data ControlGraph. All feature logic lives here.' },
        { title: 'ControlGraph', desc: 'Immutable data structure with TokenEvents, SpeakerRefs, and prosody. Versioned for compatibility.' },
        { title: 'Engine', desc: 'Transforms graphs into PCM audio. Knows nothing about emotions or styles — only synthesis.' },
      ],
    },
    {
      kind: 'data-table',
      id: 'backends',
      title: 'Backends',
      subtitle: 'Choose the right backend for your use case.',
      columns: ['Backend', 'Quality', 'Speed', 'Sample Rate', 'Install'],
      rows: [
        ['Kokoro', 'Excellent', 'Fast (GPU)', '24 kHz', 'pip install voice-soundboard[kokoro]'],
        ['Piper', 'Great', 'Fast (CPU)', '22 kHz', 'pip install voice-soundboard[piper]'],
        ['OpenAI', 'Excellent', 'API latency', 'Varies', 'pip install voice-soundboard[openai]'],
        ['ElevenLabs', 'Excellent', 'API latency', 'Varies', 'pip install voice-soundboard[elevenlabs]'],
        ['Azure', 'Excellent', 'API latency', 'Varies', 'pip install voice-soundboard[azure]'],
        ['Mock', 'N/A', 'Instant', '24 kHz', 'Built-in (testing)'],
      ],
    },
  ],
};
