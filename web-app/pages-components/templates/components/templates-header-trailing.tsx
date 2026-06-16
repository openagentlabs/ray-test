"use client";

import { LayoutGrid } from "lucide-react";
import Link from "next/link";
import type { FC } from "react";

import { buttonVariants } from "@/components/ui/button";
import { TEMPLATES_INDEX_PATH } from "@/lib/templates/template-groups";
import { cn } from "@/lib/utils";

import { TemplatesIndexUrlBadge } from "./templates-index-url-badge";

export const TemplatesHeaderTrailing: FC = () => {
  return (
    <>
      <Link
        href={TEMPLATES_INDEX_PATH}
        className={cn(
          buttonVariants({ variant: "outline", size: "sm" }),
          "hidden gap-1.5 font-medium sm:inline-flex",
        )}
      >
        <LayoutGrid className="size-4" aria-hidden />
        Template gallery
      </Link>
      <TemplatesIndexUrlBadge className="hidden lg:inline-flex" />
    </>
  );
};
