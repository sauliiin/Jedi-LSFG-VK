import { ButtonItem, Field, PanelSection, PanelSectionRow } from "@decky/ui";
import { useCallback, useEffect, useState } from "react";
import { getPluginUpdateStatus, type PluginUpdateStatus } from "../api/lsfgApi";
import { installPluginUpdate } from "../utils/pluginUpdate";

export function PluginUpdateSection() {
  const [status, setStatus] = useState<PluginUpdateStatus | null>(null);
  const [checking, setChecking] = useState(false);
  const [updating, setUpdating] = useState(false);
  const [message, setMessage] = useState("");

  const refresh = useCallback(async (force: boolean) => {
    setChecking(true);
    try {
      setStatus(await getPluginUpdateStatus(force));
    } catch (error) {
      setStatus({ success: false, error: String(error), installed_version: "", update_available: false });
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void refresh(false);
  }, [refresh]);

  const update = async () => {
    if (!status) return;
    setUpdating(true);
    setMessage(`Downloading v${status.latest_version}...`);
    try {
      setMessage(`v${await installPluginUpdate(status)} installed. Reloading the plugin...`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setUpdating(false);
    }
  };

  const installed = status?.installed_version ? `v${status.installed_version}` : "Installed version unknown";
  const description = !status
    ? "Checking GitHub..."
    : !status.success
      ? status.error || "Could not check for updates"
      : status.update_available
        ? `${installed} · v${status.latest_version} available`
        : `${installed} · up to date`;
  const size = status?.size ? ` (${Math.max(1, Math.round(status.size / 1048576))} MB)` : "";

  return (
    <PanelSection title="Plugin update">
      <PanelSectionRow>
        <Field label="Jedi LSFG-VK" description={description} />
      </PanelSectionRow>
      {status?.update_available && (
        <PanelSectionRow>
          <ButtonItem layout="below" onClick={() => void update()} disabled={updating}>
            {updating ? "Updating..." : `Update to v${status.latest_version}${size}`}
          </ButtonItem>
        </PanelSectionRow>
      )}
      {message && (
        <PanelSectionRow>
          <div style={{ fontSize: "0.85em", whiteSpace: "pre-wrap" }}>{message}</div>
        </PanelSectionRow>
      )}
      <PanelSectionRow>
        <ButtonItem layout="below" onClick={() => void refresh(true)} disabled={checking || updating}>
          {checking ? "Checking..." : "Check for updates"}
        </ButtonItem>
      </PanelSectionRow>
    </PanelSection>
  );
}
