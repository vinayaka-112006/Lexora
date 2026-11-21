export function BotanicalLogo({ size = 38, className = '' }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <rect width="48" height="48" rx="12" fill="#174C3C" />
      {/* Balance Scale Center Pillar */}
      <line x1="24" y1="12" x2="24" y2="35" stroke="#E7C98B" strokeWidth="2" strokeLinecap="round" />
      {/* Beam */}
      <path d="M15 17L24 15L33 17" stroke="#E7C98B" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {/* Left scale pan */}
      <path d="M12 25C12 27 15 28 15 28C15 28 18 27 18 25" stroke="#789B83" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="15" y1="17" x2="12" y2="25" stroke="#789B83" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="15" y1="17" x2="18" y2="25" stroke="#789B83" strokeWidth="1.2" strokeLinecap="round" />
      {/* Right scale pan */}
      <path d="M30 25C30 27 33 28 33 28C33 28 36 27 36 25" stroke="#789B83" strokeWidth="1.5" strokeLinecap="round" />
      <line x1="33" y1="17" x2="30" y2="25" stroke="#789B83" strokeWidth="1.2" strokeLinecap="round" />
      <line x1="33" y1="17" x2="36" y2="25" stroke="#789B83" strokeWidth="1.2" strokeLinecap="round" />
      {/* Botanical Leaf Motif emerging at base */}
      <path
        d="M24 35C21 31 18 29 17 26C19 26 22 28 24 31C26 28 29 26 31 26C30 29 27 31 24 35Z"
        fill="#C77B57"
        opacity="0.9"
      />
      <circle cx="24" cy="13" r="2" fill="#E7C98B" />
      <line x1="20" y1="36" x2="28" y2="36" stroke="#E7C98B" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

export function HeroIllustration() {
  return (
    <div className="hero-illustration-container">
      <svg
        viewBox="0 0 540 440"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="hero-illustration-svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="bgGlow" x1="0" y1="0" x2="540" y2="440" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#174C3C" stopOpacity="0.08" />
            <stop offset="50%" stopColor="#789B83" stopOpacity="0.12" />
            <stop offset="100%" stopColor="#E7C98B" stopOpacity="0.06" />
          </linearGradient>
          <linearGradient id="leafGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#174C3C" />
            <stop offset="100%" stopColor="#789B83" />
          </linearGradient>
          <linearGradient id="goldGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="#E7C98B" />
            <stop offset="100%" stopColor="#C77B57" />
          </linearGradient>
          <filter id="cardShadow" x="-10" y="-10" width="220" height="150" filterUnits="userSpaceOnUse">
            <feDropShadow dx="0" dy="8" stdDeviation="12" floodColor="#174C3C" floodOpacity="0.1" />
          </filter>
        </defs>

        {/* Ambient geometric background */}
        <circle cx="270" cy="220" r="180" fill="url(#bgGlow)" />
        <circle cx="270" cy="220" r="140" stroke="#789B83" strokeWidth="1" strokeDasharray="4 6" opacity="0.4" />
        <circle cx="270" cy="220" r="100" stroke="#E7C98B" strokeWidth="1" opacity="0.3" />

        {/* Centerpiece: Classical Legal Shield with Botanical Center */}
        <path
          d="M270 70C340 70 370 100 370 160C370 260 270 330 270 330C270 330 170 260 170 160C170 100 200 70 270 70Z"
          fill="#FFFFFF"
          stroke="#DCE5E0"
          strokeWidth="2"
        />
        <path
          d="M270 85C328 85 352 110 352 160C352 245 270 305 270 305C270 305 188 245 188 160C188 110 212 85 270 85Z"
          fill="#F7F5ED"
          opacity="0.8"
        />

        {/* Scales of Justice inside Shield */}
        <line x1="270" y1="110" x2="270" y2="245" stroke="#174C3C" strokeWidth="3" strokeLinecap="round" />
        <path d="M225 135L270 125L315 135" stroke="#174C3C" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="270" cy="110" r="5" fill="#E7C98B" stroke="#174C3C" strokeWidth="2" />

        {/* Left Pan */}
        <line x1="225" y1="135" x2="210" y2="185" stroke="#789B83" strokeWidth="1.5" />
        <line x1="225" y1="135" x2="240" y2="185" stroke="#789B83" strokeWidth="1.5" />
        <path d="M205 185C205 195 245 195 245 185Z" fill="#E7C98B" stroke="#174C3C" strokeWidth="1.5" />

        {/* Right Pan */}
        <line x1="315" y1="135" x2="300" y2="185" stroke="#789B83" strokeWidth="1.5" />
        <line x1="315" y1="135" x2="330" y2="185" stroke="#789B83" strokeWidth="1.5" />
        <path d="M295 185C295 195 335 195 335 185Z" fill="#E7C98B" stroke="#174C3C" strokeWidth="1.5" />

        {/* Botanical Flourish: Ashwagandha / Neem leaves rising from base */}
        <path
          d="M270 270C250 240 230 225 210 215C225 210 245 220 270 250Z"
          fill="url(#leafGrad)"
        />
        <path
          d="M270 270C290 240 310 225 330 215C315 210 295 220 270 250Z"
          fill="url(#leafGrad)"
        />
        <path
          d="M270 280C270 240 260 210 270 190C280 210 270 240 270 280Z"
          fill="#C77B57"
        />

        {/* Floating Stat Card 1: Patents Act 1970 */}
        <g transform="translate(40, 100)">
          <rect width="160" height="68" rx="12" fill="#FFFFFF" stroke="#DCE5E0" strokeWidth="1.5" filter="url(#cardShadow)" />
          <circle cx="28" cy="34" r="16" fill="#EEF4F0" />
          <path d="M24 34L27 37L33 30" stroke="#174C3C" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          <text x="52" y="28" fill="#174C3C" fontSize="12" fontWeight="700" fontFamily="system-ui, sans-serif">Section 3(p)</text>
          <text x="52" y="44" fill="#718078" fontSize="10" fontFamily="system-ui, sans-serif">Traditional Knowledge</text>
        </g>

        {/* Floating Stat Card 2: Biological Diversity Act */}
        <g transform="translate(340, 260)">
          <rect width="160" height="68" rx="12" fill="#FFFFFF" stroke="#DCE5E0" strokeWidth="1.5" filter="url(#cardShadow)" />
          <circle cx="28" cy="34" r="16" fill="#FDF8F0" />
          <path d="M28 24C24 28 24 36 28 38C32 36 32 28 28 24Z" fill="#C77B57" />
          <text x="52" y="28" fill="#174C3C" fontSize="12" fontWeight="700" fontFamily="system-ui, sans-serif">BDA Section 7</text>
          <text x="52" y="44" fill="#718078" fontSize="10" fontFamily="system-ui, sans-serif">SBB Prior Intimation</text>
        </g>

        {/* Decorative nodes */}
        <circle cx="120" cy="270" r="4" fill="#789B83" opacity="0.6" />
        <circle cx="430" cy="120" r="4" fill="#C77B57" opacity="0.6" />
        <line x1="120" y1="270" x2="150" y2="250" stroke="#789B83" strokeWidth="1" strokeDasharray="3 3" opacity="0.5" />
        <line x1="400" y1="140" x2="430" y2="120" stroke="#C77B57" strokeWidth="1" strokeDasharray="3 3" opacity="0.5" />
      </svg>
    </div>
  )
}

