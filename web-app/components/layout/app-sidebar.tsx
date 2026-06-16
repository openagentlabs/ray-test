"use client";

import { Fragment } from "react";

import { ChevronLeft, PanelLeft } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { AppPublicConfig } from "@/lib/config/app-config-public";
import { NavigationIconResolver } from "@/lib/navigation/navigation-icon-resolver";
import { SidebarPreferences } from "@/lib/storage/sidebar-preferences";
import type { NavItemDefinition } from "@/lib/types/nav-item-definition";
import { cn } from "@/lib/utils";

function navItemMatchesPath(
  pathname: string,
  item: NavItemDefinition,
): boolean {
  if (pathname === item.href) {
    return true;
  }
  if (item.href === "/") {
    return false;
  }
  return pathname.startsWith(`${item.href}/`);
}

function resolveActiveNavItemId(
  pathname: string,
  items: readonly NavItemDefinition[],
): string | undefined {
  const matches = items.filter((item) => navItemMatchesPath(pathname, item));
  if (matches.length === 0) {
    return undefined;
  }
  return matches.reduce((longest, cur) =>
    cur.href.length > longest.href.length ? cur : longest,
  matches[0]!).id;
}

interface NavRenderItem {
  readonly item: NavItemDefinition;
  readonly index: number;
  readonly showGroupHeading: boolean;
  readonly showSubgroupHeading: boolean;
  readonly showGroupDivider: boolean;
}

function buildNavRenderItems(
  items: readonly NavItemDefinition[],
  collapsed: boolean,
): readonly NavRenderItem[] {
  let previousGroup: string | undefined;
  let previousSubgroup: string | undefined;

  return items.map((item, index) => {
    const showGroupHeading =
      !collapsed &&
      item.groupTitle !== undefined &&
      item.groupTitle !== previousGroup;
    const showSubgroupHeading =
      !collapsed &&
      item.subgroupTitle !== undefined &&
      item.subgroupTitle !== previousSubgroup;
    const showGroupDivider = showGroupHeading && index > 0;

    if (item.groupTitle !== undefined) {
      previousGroup = item.groupTitle;
    } else {
      previousGroup = undefined;
    }
    if (item.subgroupTitle !== undefined) {
      previousSubgroup = item.subgroupTitle;
    } else {
      previousSubgroup = undefined;
    }

    return {
      item,
      index,
      showGroupHeading,
      showSubgroupHeading,
      showGroupDivider,
    };
  });
}

interface AppSidebarProps {
  readonly navigationItems: readonly NavItemDefinition[];
}

export function AppSidebar({ navigationItems }: AppSidebarProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const iconResolver = useMemo(() => new NavigationIconResolver(), []);
  const activeNavItemId = useMemo(
    () => resolveActiveNavItemId(pathname, navigationItems),
    [pathname, navigationItems],
  );
  const navRenderItems = useMemo(
    () => buildNavRenderItems(navigationItems, collapsed),
    [navigationItems, collapsed],
  );

  useEffect(() => {
    queueMicrotask(() => {
      setCollapsed(SidebarPreferences.readCollapsed());
      setHydrated(true);
    });
  }, []);

  const persistCollapsed = (next: boolean) => {
    setCollapsed(next);
    SidebarPreferences.writeCollapsed(next);
  };

  return (
    <aside
      className={cn(
        "flex h-full shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground transition-[width] duration-200 ease-out",
        collapsed ? "w-[4.25rem]" : "w-60",
      )}
      data-collapsed={collapsed ? "true" : "false"}
    >
      <div
        className={cn(
          "flex h-14 items-center border-b border-sidebar-border px-3",
          collapsed ? "justify-center" : "justify-between gap-2",
        )}
      >
        {!collapsed ? (
          <span className="truncate text-sm font-semibold tracking-tight">
            {AppPublicConfig.applicationName}
          </span>
        ) : null}
        <Tooltip>
          <TooltipTrigger
            render={
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                className="shrink-0 text-sidebar-foreground"
                onClick={() => persistCollapsed(!collapsed)}
                aria-expanded={!collapsed}
                aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              >
                {collapsed ? (
                  <PanelLeft className="size-4" />
                ) : (
                  <ChevronLeft className="size-4" />
                )}
              </Button>
            }
          />
          <TooltipContent side="right" align="center">
            {collapsed ? "Expand" : "Collapse"}
          </TooltipContent>
        </Tooltip>
      </div>

      <ScrollArea className="flex-1">
        <nav
          className="flex flex-col gap-0.5 p-2"
          aria-label="Workspace navigation"
        >
          {navRenderItems.map(
            ({
              item,
              index,
              showGroupHeading,
              showSubgroupHeading,
              showGroupDivider,
            }) => {
              const Icon = iconResolver.resolve(item.id);
              const active = item.id === activeNavItemId;

              const linkClass = cn(
                "flex items-center gap-2 rounded-md px-2 py-2 text-sm font-medium transition-colors",
                active
                  ? "bg-sidebar-accent text-sidebar-accent-foreground"
                  : "text-sidebar-foreground hover:bg-sidebar-accent/80 hover:text-sidebar-accent-foreground",
                collapsed ? "justify-center px-0" : "",
              );

              const linkInner = (
                <>
                  <Icon className="size-4 shrink-0" aria-hidden />
                  {!collapsed ? (
                    <span className="truncate">{item.title}</span>
                  ) : null}
                </>
              );

              const linkEl = (
                <Link href={item.href} className={linkClass}>
                  {linkInner}
                </Link>
              );

              return (
                <Fragment key={item.id}>
                  {showGroupDivider ? (
                    <div
                      className="mx-1 my-2 border-t border-sidebar-border/80"
                      aria-hidden
                    />
                  ) : null}
                  {showGroupHeading ? (
                    <div
                      className={cn(
                        "px-2 pb-1 pt-1 text-[11px] font-semibold tracking-wide text-sidebar-foreground/75",
                        !showGroupDivider && index === 0 ? "pt-0" : null,
                      )}
                      role="presentation"
                    >
                      {item.groupTitle}
                    </div>
                  ) : null}
                  {showSubgroupHeading ? (
                    <div
                      className="px-2 pb-0.5 pt-0.5 text-[11px] font-medium text-sidebar-foreground/60"
                      role="presentation"
                    >
                      {item.subgroupTitle}
                    </div>
                  ) : null}
                  {collapsed && hydrated ? (
                    <Tooltip>
                      <TooltipTrigger
                        render={
                          <Link href={item.href} className={linkClass}>
                            {linkInner}
                          </Link>
                        }
                      />
                      <TooltipContent side="right" align="center">
                        {item.title}
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    linkEl
                  )}
                </Fragment>
              );
            },
          )}
        </nav>
      </ScrollArea>
    </aside>
  );
}
