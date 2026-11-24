"use client";

import { useTranslation } from "react-i18next";
import {
  SettingsPageHeader,
  SettingSection,
  SettingRow,
} from "@/components/settings/shared";

export default function CustomerAboutSettingsSection() {
  const { t } = useTranslation();

  return (
    <div className="pb-8">
      <SettingsPageHeader
        title={t("Help & About")}
        description={t("Learn more about DrChenAI and get help with your experience.")}
      />

      <section className="mb-8 rounded-2xl border border-[var(--border)] bg-[var(--card)] p-6">
        <h2 className="text-3xl font-semibold tracking-tight">DrChenAI</h2>
        <p className="mt-2 text-sm text-[var(--muted-foreground)]">
          {t("Your AI-powered learning companion.")}
        </p>
        <p className="mt-4 text-sm leading-relaxed">
          {t("Explore new ideas, understand complex topics, and learn at your own pace with personalized AI assistance.")}
        </p>
      </section>

      <SettingSection title={t("Help center")}>
        <SettingRow
          title={t("Getting started")}
            control={null}
          description={t("Start a conversation, ask a question, or explore the available learning tools.")}
        />
        <SettingRow
          title={t("Voice assistance")}
            control={null}
          description={t("Use the microphone to ask questions and the speaker to listen to responses.")}
        />
        <SettingRow
          title={t("Troubleshooting")}
            control={null}
          description={t("If a feature is not responding, refresh the page and try again.")}
        />
      </SettingSection>

      <SettingSection title={t("Privacy & data")}>
        <SettingRow
          title={t("Manage your conversations")}
          description={t("View, restore, or delete archived conversations.")}
          control={
            <a href="/settings/archive" className="text-sm font-medium underline">
              {t("Data controls")}
            </a>
          }
        />
      </SettingSection>

      <SettingSection title={t("About DrChenAI")}>
        <SettingRow
          title={t("Product")}
          control={<span className="text-sm">DrChenAI</span>}
        />
        <SettingRow
          title={t("Developed by")}
          control={<span className="text-sm">DeepBrain Academy</span>}
        />
      </SettingSection>
    </div>
  );
}
