"use client";

import { Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const triggerClassName = cn(
  "inline-flex size-9 shrink-0 items-center justify-center rounded-full",
  "border border-border/60 bg-muted/40 text-muted-foreground",
  "shadow-sm backdrop-blur-sm",
  "transition-[color,background-color,border-color,box-shadow,transform] duration-150",
  "hover:border-border hover:bg-muted/70 hover:text-foreground hover:shadow",
  "active:scale-[0.97]",
  "outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ring-offset-background",
  "disabled:pointer-events-none disabled:opacity-50",
);

export function ThemeToggle() {
  const { setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    queueMicrotask(() => {
      setMounted(true);
    });
  }, []);

  if (!mounted) {
    return (
      <button
        type="button"
        disabled
        className={triggerClassName}
        aria-hidden
      >
        <Sun className="size-[1.05rem] opacity-40" strokeWidth={1.75} />
      </button>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className={triggerClassName}>
        {isDark ? (
          <Moon className="size-[1.05rem]" strokeWidth={1.75} aria-hidden />
        ) : (
          <Sun className="size-[1.05rem]" strokeWidth={1.75} aria-hidden />
        )}
        <span className="sr-only">Appearance</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" sideOffset={8} className="min-w-[10.5rem]">
        <DropdownMenuLabel className="text-xs font-medium text-muted-foreground">
          Appearance
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={() => setTheme("light")}>
          <Sun className="size-4 text-amber-500/90" strokeWidth={1.75} />
          Light
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")}>
          <Moon className="size-4 text-sky-400/90" strokeWidth={1.75} />
          Dark
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
