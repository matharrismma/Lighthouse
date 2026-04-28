# Four Gates Decision Validation Protocol

A live demo of the Four Gates framework — a sequential decision validation protocol that checks proposed actions against four gates: **RED** (absolute prohibitions), **FLOOR** (protective minimums), **BROTHERS** (community witness), and **GOD** (alignment with purpose and authority).

Fail-fast: if any gate halts, the remaining gates don't run.

## Quick Start

### 1. Install dependencies

```bash
npm install
```

### 2. Set your API key

Copy the environment template and add your Anthropic API key:

```bash
cp .env.example .env
```

Edit `.env` and set your key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Get a key at https://console.anthropic.com/

### 3. Run (development)

```bash
npm run dev
```

This starts both the backend proxy (port 3001) and the React frontend (port 3000). Open http://localhost:3000.

### 4. Build for production

```bash
npm run build
```

Serve the `build/` folder with any static host (Netlify, Vercel, etc.) and deploy the proxy server separately, or use a platform that supports both (Railway, Render, Fly.io).

## Architecture

```
Browser (React) → /api/validate (Express proxy) → Anthropic API
```

The API key never touches the frontend. The proxy server holds it server-side and forwards requests to Claude.

## Project Structure

```
four-gates-demo/
├── public/
│   └── index.html
├── server/
│   └── proxy.js          # Express proxy (holds API key)
├── src/
│   ├── FourGatesDemo.js  # Main component
│   └── index.js          # React entry point
├── .env.example
├── package.json
└── README.md
```

## Deployment Options

**Simplest:** Deploy to Render or Railway as a single service — they can serve both the static build and the Node proxy.

**Split:** Host the React build on Netlify/Vercel and the proxy on any Node host. Update the fetch URL in FourGatesDemo.js to point to your proxy's deployed URL.

## License

Private — not for redistribution without permission.
