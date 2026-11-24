"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchAuthStatus, type AuthStatus } from "@/lib/auth";
import { SettingsPageHeader, SettingSection, SettingRow } from "@/components/settings/shared";

export default function CustomerAccountSettingsSection() {
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    void fetchAuthStatus().then((value) => {
      if (active) {
        setStatus(value);
        setLoading(false);
      }
    });
    return () => { active = false; };
  }, []);

  return (
    <div className="pb-8">
      <SettingsPageHeader
        title="Account"
        description="Manage your DrChenAI account and profile."
      />

      {loading ? (
        <p className="text-sm">Loading account...</p>
      ) : status?.enabled && status?.authenticated ? (
        <SettingSection title="Your account">
          <SettingRow
            title="Username"
            control={<span className="text-sm">{status.username}</span>}
          />
          <SettingRow
            title="Profile and security"
            description="Manage your profile picture and available account security options."
            control={
              <Link href="/profile" className="text-sm font-medium underline">
                Manage profile
              </Link>
            }
          />
        </SettingSection>
      ) : (
        <p className="text-sm text-[var(--muted-foreground)]">
          {status === null
            ? "Account information is currently unavailable."
            : "Account management requires an authenticated account."}
        </p>
      )}
    </div>
  );
}
