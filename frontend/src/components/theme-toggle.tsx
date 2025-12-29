"use client";

import { Sun, Moon } from "lucide-react";
import { useTheme } from "@/lib/theme-context";
import clsx from "clsx";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className={clsx(
        "relative p-2 rounded-lg transition-all duration-300 group",
        theme === "dark"
          ? "bg-surface-800 hover:bg-surface-700 text-surface-300 hover:text-amber-400"
          : "bg-slate-100 hover:bg-slate-200 text-slate-600 hover:text-amber-500",
        className
      )}
      title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      aria-label="Toggle theme"
    >
      <div className="relative w-5 h-5">
        {/* Sun icon */}
        <Sun
          size={20}
          className={clsx(
            "absolute inset-0 transition-all duration-300",
            theme === "dark"
              ? "opacity-0 rotate-90 scale-0"
              : "opacity-100 rotate-0 scale-100"
          )}
        />
        {/* Moon icon */}
        <Moon
          size={20}
          className={clsx(
            "absolute inset-0 transition-all duration-300",
            theme === "dark"
              ? "opacity-100 rotate-0 scale-100"
              : "opacity-0 -rotate-90 scale-0"
          )}
        />
      </div>
    </button>
  );
}

