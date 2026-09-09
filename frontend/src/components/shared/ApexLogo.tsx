import React from 'react'

interface ApexLogoProps {
  size?: number
  className?: string
}

export const ApexLogo: React.FC<ApexLogoProps> = ({ size = 42, className = '' }) => {
  return (
    <div
      className={`apex-logo-container ${className}`}
      style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        flexShrink: 0,
      }}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ filter: 'drop-shadow(0 0 12px rgba(6, 182, 212, 0.45))' }}
      >
        <defs>
          <linearGradient id="apexGrad1" x1="4" y1="44" x2="24" y2="4" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#3b82f6" />
            <stop offset="100%" stopColor="#06b6d4" />
          </linearGradient>
          <linearGradient id="apexGrad2" x1="24" y1="4" x2="44" y2="44" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#06b6d4" />
            <stop offset="100%" stopColor="#8b5cf6" />
          </linearGradient>
          <linearGradient id="apexGradGlow" x1="24" y1="12" x2="24" y2="38" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.8" />
            <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.1" />
          </linearGradient>
        </defs>

        {/* Outer Hex/Apex Shield Silhouette */}
        <path
          d="M24 4L42 14V34L24 44L6 34V14L24 4Z"
          fill="rgba(15, 23, 42, 0.7)"
          stroke="url(#apexGrad1)"
          strokeWidth="2"
          strokeLinejoin="round"
        />

        {/* Inner Facet / Prism Apex */}
        <path
          d="M24 6L39 15.5L24 24L9 15.5L24 6Z"
          fill="url(#apexGradGlow)"
          stroke="#06b6d4"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* Left Refraction Vector */}
        <path
          d="M9 16V32L24 41V24L9 16Z"
          fill="rgba(59, 130, 246, 0.18)"
          stroke="url(#apexGrad1)"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* Right Refraction Vector */}
        <path
          d="M39 16V32L24 41V24L39 16Z"
          fill="rgba(139, 92, 246, 0.22)"
          stroke="url(#apexGrad2)"
          strokeWidth="1.5"
          strokeLinejoin="round"
        />

        {/* Center Illuminated Apex Beam */}
        <line
          x1="24"
          y1="6"
          x2="24"
          y2="41"
          stroke="#e0f2fe"
          strokeWidth="2"
          strokeLinecap="round"
          style={{ opacity: 0.85 }}
        />
        
        {/* Core Jewel Sparkle */}
        <circle cx="24" cy="24" r="2.5" fill="#ffffff" style={{ filter: 'drop-shadow(0 0 6px #38bdf8)' }} />
      </svg>
    </div>
  )
}
