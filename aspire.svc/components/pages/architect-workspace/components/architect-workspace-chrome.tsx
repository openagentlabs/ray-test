"use client";

import Link from "next/link";
import {
  ChevronDown,
  CircleUser,
  Filter,
  Home,
  MoreHorizontal,
  Plus,
  RefreshCw,
  UserPlus,
} from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

import type { ArchitectWorkspaceTab } from "../architect-mock-data";
import { architectPanelClassName } from "../architect-panel-styles";

export interface ArchitectWorkspaceChromeProps {
  readonly activeTab: ArchitectWorkspaceTab;
  readonly tabLabels: readonly ArchitectWorkspaceTab[];
  readonly advancedFiltersOpen: boolean;
  readonly onTabChange: (tab: ArchitectWorkspaceTab) => void;
  readonly onAdvancedFiltersOpenChange: (open: boolean) => void;
  readonly onRefreshMockData: () => void;
  readonly onAddTabRequest: () => void;
}

export function ArchitectWorkspaceChrome({
  activeTab,
  tabLabels,
  advancedFiltersOpen,
  onTabChange,
  onAdvancedFiltersOpenChange,
  onRefreshMockData,
  onAddTabRequest,
}: ArchitectWorkspaceChromeProps) {
  return (
    <div className={cn(architectPanelClassName(), "overflow-hidden")}>
      <div className="border-b border-border bg-muted/40 px-4 py-2">
        <p className="text-xs font-medium text-muted-foreground">
          Demo organisation · Care coordination workspace (mock branding strip)
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <Tooltip>
          <TooltipTrigger
            render={
              <Link
                href="/"
                aria-label="Home"
                className={cn(buttonVariants({ variant: "outline", size: "icon-sm" }))}
              >
                <Home className="size-4" />
              </Link>
            }
          />
          <TooltipContent>Return to workspace home</TooltipContent>
        </Tooltip>

        <DropdownMenu>
          <DropdownMenuTrigger
            render={<Button variant="secondary" size="sm" className="gap-1" />}
          >
            New
            <ChevronDown className="size-3.5 opacity-70" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="start" className="min-w-48">
            <DropdownMenuLabel>Create</DropdownMenuLabel>
            <DropdownMenuItem>New case</DropdownMenuItem>
            <DropdownMenuItem>New enrollment</DropdownMenuItem>
            <DropdownMenuItem>New task</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

        <Tooltip>
          <TooltipTrigger
            render={
              <Link
                href="/pages/users/add"
                className={cn(
                  buttonVariants({ variant: "default", size: "sm" }),
                  "gap-1.5 font-medium",
                )}
              >
                <UserPlus className="size-3.5 opacity-90" aria-hidden />
                Add User
              </Link>
            }
          />
          <TooltipContent>Open the add user page</TooltipContent>
        </Tooltip>

        <Separator orientation="vertical" className="hidden h-6 sm:block" />

        <div className="hidden items-center gap-1 md:flex">
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="sm" className="text-muted-foreground">
                  Reporting
                  <ChevronDown className="size-3.5 opacity-70" />
                </Button>
              }
            />
            <DropdownMenuContent align="start">
              <DropdownMenuItem>Utilization summary (mock)</DropdownMenuItem>
              <DropdownMenuItem>Gap-in-care report (mock)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="sm" className="text-muted-foreground">
                  Analytics
                  <ChevronDown className="size-3.5 opacity-70" />
                </Button>
              }
            />
            <DropdownMenuContent align="start">
              <DropdownMenuItem>Cohort explorer (mock)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button variant="ghost" size="sm" className="text-muted-foreground">
                  Administration
                  <ChevronDown className="size-3.5 opacity-70" />
                </Button>
              }
            />
            <DropdownMenuContent align="start">
              <DropdownMenuItem>Roles & permissions (mock)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="ml-auto flex flex-wrap items-center gap-1">
          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  type="button"
                  onClick={onRefreshMockData}
                >
                  <RefreshCw className="size-4" />
                </Button>
              }
            />
            <TooltipContent>Refresh mock data</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  type="button"
                  aria-expanded={advancedFiltersOpen}
                  aria-controls="advanced-filters"
                  onClick={() => onAdvancedFiltersOpenChange(!advancedFiltersOpen)}
                >
                  <Filter className="size-4" />
                </Button>
              }
            />
            <TooltipContent>Show or hide advanced filters</TooltipContent>
          </Tooltip>

          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon-sm" aria-label="More actions" />}
            >
              <MoreHorizontal className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem>Export view (mock)</DropdownMenuItem>
              <DropdownMenuItem>Print (mock)</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>

          <DropdownMenu>
            <DropdownMenuTrigger
              render={<Button variant="ghost" size="icon-sm" aria-label="User menu" />}
            >
              <CircleUser className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="min-w-44">
              <DropdownMenuLabel>Signed in</DropdownMenuLabel>
              <DropdownMenuItem>My Clipboard</DropdownMenuItem>
              <DropdownMenuItem>Change Password</DropdownMenuItem>
              <DropdownMenuItem>About</DropdownMenuItem>
              <DropdownMenuItem>Help</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive">Logout</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="flex items-center gap-1 overflow-x-auto border-t border-border bg-muted/20 px-2 py-1.5">
        {tabLabels.map((label) => (
          <Button
            key={label}
            type="button"
            size="sm"
            variant={activeTab === label ? "secondary" : "ghost"}
            className={cn(
              "shrink-0 rounded-md",
              activeTab === label && "bg-background shadow-sm ring-1 ring-border",
            )}
            onClick={() => onTabChange(label)}
          >
            {label}
          </Button>
        ))}
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                variant="outline"
                size="icon-sm"
                className="shrink-0"
                type="button"
                onClick={onAddTabRequest}
              >
                <Plus className="size-4" />
              </Button>
            }
          />
          <TooltipContent>Add or remove tabs (mock)</TooltipContent>
        </Tooltip>
      </div>
    </div>
  );
}
