'use client';

import { useTheme } from '@/components/ThemeProvider';
import { Moon, Sun, Bell, LogOut, Settings } from 'lucide-react';
import { useSession, signOut } from 'next-auth/react';
import { Button } from '@/components/ui/button';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

export function DashboardHeader() {
  const { darkMode, setDarkMode } = useTheme();
  const { data: session } = useSession();

  const userInitials = session?.user?.name
    ? session.user.name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2)
    : '?';

  return (
    <header className="h-16 border-b border-border-subtle bg-surface-elevated/80 backdrop-blur-xl flex items-center justify-end px-6 gap-3">
      {/* Notifications */}
      <Button
        variant="ghost"
        size="icon"
        className="relative"
        aria-label="Notifications"
      >
        <Bell className="h-5 w-5 text-text-secondary" />
        <span className="absolute top-1.5 right-1.5 h-2 w-2 bg-brand-primary rounded-full" />
      </Button>

      {/* Theme toggle */}
      <Button
        variant="ghost"
        size="icon"
        onClick={() => setDarkMode(!darkMode)}
        aria-label="Toggle theme"
      >
        {darkMode ? (
          <Sun className="h-5 w-5 text-text-secondary" />
        ) : (
          <Moon className="h-5 w-5 text-text-secondary" />
        )}
      </Button>

      {/* User menu */}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" className="relative h-9 w-9 rounded-full">
            <Avatar className="h-8 w-8">
              <AvatarImage src={session?.user?.image ?? undefined} alt={session?.user?.name ?? ''} />
              <AvatarFallback className="text-xs">{userInitials}</AvatarFallback>
            </Avatar>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent className="w-56" align="end" forceMount>
          <DropdownMenuLabel className="font-normal">
            <div className="flex flex-col space-y-1">
              <p className="text-sm font-medium leading-none">
                {session?.user?.name ?? 'Account'}
              </p>
              <p className="text-xs leading-none text-muted-foreground">
                {session?.user?.email ?? ''}
              </p>
            </div>
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild>
            <a href="/dashboard/settings" className="cursor-pointer">
              <Settings className="mr-2 h-4 w-4" />
              Settings
            </a>
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            className="cursor-pointer text-destructive focus:text-destructive"
            onClick={() => signOut({ callbackUrl: '/' })}
          >
            <LogOut className="mr-2 h-4 w-4" />
            Sign out
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
