# InsurAI Frontend

A modern, beautiful frontend UI for the Universal Insurance AI Agent platform.

## Features

- **Dashboard** - Overview of all policies with stats and quick actions
- **Coverage Check** - AI-powered instant coverage verification with guardrail logic
- **Policy Management** - View, search, and manage ingested policies
- **Upload** - Ingest new policies via PDF upload or text paste
- **Real-time Feedback** - Visual status indicators and financial context

## Tech Stack

- **Next.js 14** - App Router with TypeScript
- **Tailwind CSS** - Utility-first styling with custom design system
- **Lucide Icons** - Beautiful open source icons
- **Google Fonts** - Outfit (sans) + JetBrains Mono (mono)

## Getting Started

### Prerequisites

- Node.js 18+
- Backend API running on `http://localhost:8000`

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### Production Build

```bash
npm run build
npm start
```

## Project Structure

```
frontend/
├── src/
│   ├── app/                 # Next.js App Router pages
│   │   ├── page.tsx         # Dashboard
│   │   ├── coverage/        # Coverage check page
│   │   ├── policies/        # Policy list & detail pages
│   │   └── upload/          # Upload policy page
│   ├── components/          # Reusable React components
│   │   ├── Sidebar.tsx      # Navigation sidebar
│   │   └── StatusBadge.tsx  # Coverage status indicator
│   └── lib/                 # Utilities
│       ├── api.ts           # API client
│       └── types.ts         # TypeScript types
├── tailwind.config.ts       # Tailwind configuration
└── next.config.js           # Next.js configuration
```

## Design System

### Colors

- **Brand** - Coral/Orange (#f97316) for primary actions
- **Surface** - Slate-based dark theme
- **Status**:
  - Covered: Emerald (#10b981)
  - Not Covered: Rose (#ef4444)
  - Conditional: Amber (#f59e0b)
  - Unknown: Gray (#6b7280)

### Typography

- **Headings** - Outfit (modern geometric sans-serif)
- **Code/IDs** - JetBrains Mono

## API Integration

The frontend proxies API requests to the backend:

- `/api/*` → `http://localhost:8000/api/*`

Configure the backend URL in `next.config.js` if needed.

