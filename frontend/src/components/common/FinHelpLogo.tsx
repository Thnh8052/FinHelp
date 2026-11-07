import React from "react";

interface FinHelpLogoProps {
  size?: "sm" | "md" | "lg" | "xl";
  showText?: boolean;
  className?: string;
  onClick?: () => void;
}

export const FinHelpLogo: React.FC<FinHelpLogoProps> = ({
  size = "md",
  showText = true,
  className = "",
  onClick,
}) => {
  const sizeMap = {
    sm: { icon: 24, font: "text-sm", gap: "gap-1.5" },
    md: { icon: 32, font: "text-base", gap: "gap-2.5" },
    lg: { icon: 40, font: "text-xl", gap: "gap-3" },
    xl: { icon: 48, font: "text-2xl", gap: "gap-3.5" },
  };

  const currentSize = sizeMap[size] || sizeMap.md;

  return (
    <div
      className={`inline-flex items-center ${currentSize.gap} select-none ${
        onClick ? "cursor-pointer hover:opacity-90 transition-opacity" : ""
      } ${className}`}
      onClick={onClick}
    >
      {/* Dynamic FinHelp SVG Emblem */}
      <svg
        width={currentSize.icon}
        height={currentSize.icon}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="flex-shrink-0"
      >
        <defs>
          {/* Main Gradient */}
          <linearGradient id="fhBlueCyanGrad" x1="2" y1="2" x2="38" y2="38" gradientUnits="userSpaceOnUse">
            <stop stopColor="#2563EB" />
            <stop offset="0.6" stopColor="#1D4ED8" />
            <stop offset="1" stopColor="#0284C7" />
          </linearGradient>

          {/* Accent Glow */}
          <linearGradient id="fhSparkGrad" x1="25" y1="6" x2="35" y2="16" gradientUnits="userSpaceOnUse">
            <stop stopColor="#FDE047" />
            <stop offset="1" stopColor="#F59E0B" />
          </linearGradient>

          {/* Glass Overlay */}
          <linearGradient id="fhGlassOverlay" x1="0" y1="0" x2="40" y2="20" gradientUnits="userSpaceOnUse">
            <stop stopColor="white" stopOpacity="0.25" />
            <stop offset="1" stopColor="white" stopOpacity="0.02" />
          </linearGradient>
        </defs>

        {/* Squircle Background */}
        <rect width="40" height="40" rx="11" fill="url(#fhBlueCyanGrad)" />
        <rect width="40" height="40" rx="11" fill="url(#fhGlassOverlay)" stroke="rgba(255,255,255,0.2)" strokeWidth="1" />

        {/* Ascending Financial Columns (Balance / Income Bars) */}
        <path
          d="M8 29V23C8 22.4477 8.44772 22 9 22H11C11.5523 22 12 22.4477 12 23V29C12 29.5523 11.5523 30 11 30H9C8.44772 30 8 29.5523 8 29Z"
          fill="white"
          fillOpacity="0.75"
        />
        <path
          d="M14 29V18C14 17.4477 14.4477 17 15 17H17C17.5523 17 18 17.4477 18 18V29C18 29.5523 17.5523 30 17 30H15C14.4477 30 14 29.5523 14 29Z"
          fill="white"
          fillOpacity="0.88"
        />
        <path
          d="M20 29V13C20 12.4477 20.4477 12 21 12H23C23.5523 12 24 12.4477 24 13V29C24 29.5523 23.5523 30 23 30H21C20.4477 30 20 29.5523 20 29Z"
          fill="white"
        />

        {/* Upward Growth Trendline */}
        <path
          d="M7 23.5L14 17.5L20 20L30 9.5"
          stroke="#93C5FD"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />

        {/* AI Insight Sparkle (✦) at the Summit */}
        <path
          d="M30 6.5L30.8 9.5L34 10.3L30.8 11.1L30 14L29.2 11.1L26 10.3L29.2 9.5L30 6.5Z"
          fill="url(#fhSparkGrad)"
        />
      </svg>

      {/* Brand Name Typography */}
      {showText && (
        <div className="flex flex-col leading-none">
          <div className={`font-extrabold tracking-tight ${currentSize.font} font-sans`}>
            <span className="text-white">Fin</span>
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-sky-300">
              Help
            </span>
          </div>
        </div>
      )}
    </div>
  );
};

export default FinHelpLogo;

