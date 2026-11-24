"use client";

import { useTranslation } from "react-i18next";
import { SettingsPageHeader } from "@/components/settings/shared";
import { VoicePlaybackPrefs } from "./models/VoicePlaybackPrefs";

export default function CustomerVoiceSettingsSection() {
  const { t } = useTranslation();

  return (
    <div>
      <SettingsPageHeader
        title={t("Voice")}
        description={t("Personalize how DrChenAI speaks and reads responses aloud.")}
      />
      <VoicePlaybackPrefs />
    </div>
  );
}
