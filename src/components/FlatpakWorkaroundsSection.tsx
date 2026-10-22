import { ButtonItem, PanelSectionRow, ToggleField } from "@decky/ui";
import { useEffect, useState } from "react";
import { RiArrowDownSFill, RiArrowUpSFill } from "react-icons/ri";
import type { WorkaroundState } from "../api/lsfgApi";
import t from "../i18n/i18n";

interface Props {
  state: WorkaroundState;
  disabled?: boolean;
  onChange: (state: WorkaroundState) => Promise<boolean>;
}

const WORKAROUNDS_COLLAPSED_KEY = "lsfg-flatpak-workarounds-collapsed-v1";

export function FlatpakWorkaroundsSection({ state, disabled = false, onChange }: Props) {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem(WORKAROUNDS_COLLAPSED_KEY) !== "false";
    } catch {
      return true;
    }
  });

  useEffect(() => {
    try {
      localStorage.setItem(WORKAROUNDS_COLLAPSED_KEY, String(collapsed));
    } catch {}
  }, [collapsed]);

  const update = (field: keyof WorkaroundState, value: boolean | number) => {
    void onChange({ ...state, [field]: value });
  };

  return (
    <>
      <PanelSectionRow>
        <div
          style={{
            fontSize: "14px",
            fontWeight: "bold",
            marginTop: "8px",
            marginBottom: "6px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.2)",
            paddingBottom: "3px",
            color: "white",
          }}
        >
          {t("CONFIG_WORKAROUNDS_TITLE", "Workarounds")}
        </div>
      </PanelSectionRow>
      <PanelSectionRow>
        <ButtonItem
          layout="below"
          bottomSeparator={collapsed ? "standard" : "none"}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? <RiArrowDownSFill /> : <RiArrowUpSFill />}
        </ButtonItem>
      </PanelSectionRow>
      {!collapsed && (
        <>
          <PanelSectionRow>
            <ToggleField
              label={t("CONFIG_DISABLE_STEAMDECK_MODE", "Disable Steam Deck Mode")}
              description={t("CONFIG_DISABLE_STEAMDECK_MODE_DESC", "Disables a game-specific Steam Deck compatibility switch. Requires app restart to apply.")}
              checked={state.disableSteamdeckMode}
              onChange={(value) => update("disableSteamdeckMode", value)}
              disabled={disabled}
            />
          </PanelSectionRow>
          <PanelSectionRow>
            <ToggleField
              label={t("CONFIG_ENABLE_ZINK", "Force Zink for OpenGL Games")}
              description={t("CONFIG_ENABLE_ZINK_DESC", "Uses Mesa's Zink OpenGL-to-Vulkan driver. May cause crashes or freezes. Requires app restart to apply.")}
              checked={state.enableZink}
              onChange={(value) => update("enableZink", value)}
              disabled={disabled}
            />
          </PanelSectionRow>
        </>
      )}
    </>
  );
}
