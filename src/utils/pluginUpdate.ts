import { toaster } from "@decky/api";
import { getPluginUpdateStatus, installPluginUpdateRelease, type PluginUpdateStatus } from "../api/lsfgApi";

const PLUGIN_NAME = "Jedi LSFG-VK";

interface DeckyBackend {
  call?: (route: string, ...args: unknown[]) => Promise<unknown>;
}

/**
 * The backend downloads the release ZIP, checks its SHA-256 and writes it over
 * the plugin; then Decky reloads the plugin. Decky's own install prompt opens in
 * the main window and never showed from the Quick Access menu.
 * Resolves with the installed version, or rejects with what went wrong.
 */
export async function installPluginUpdate(status: PluginUpdateStatus): Promise<string> {
  if (!status.update_available) throw new Error("No update is available");
  const result = await installPluginUpdateRelease();
  if (!result.success) {
    throw new Error(`${result.error || "Update failed"}${status.url ? `\n\nOr install from URL in Decky's settings: ${status.url}` : ""}`);
  }
  const version = result.version || status.latest_version || "";
  const backend = (window as unknown as { DeckyBackend?: DeckyBackend }).DeckyBackend;
  if (typeof backend?.call !== "function") {
    throw new Error(`v${version} installed. Restart Decky (or the Steam Deck) to load it.`);
  }
  try {
    await backend.call("loader/reload_plugin", result.plugin_name || status.plugin_name || PLUGIN_NAME);
  } catch {
    throw new Error(`v${version} installed. Restart Decky (or the Steam Deck) to load it.`);
  }
  return version;
}

/** One check when the plugin loads; selecting the toast starts the update. */
export async function notifyPluginUpdate(): Promise<void> {
  try {
    const status = await getPluginUpdateStatus(false);
    if (!status.success || !status.update_available) return;
    toaster.toast({
      title: `${PLUGIN_NAME} ${status.latest_version} available`,
      body: "Select to update",
      onClick: () => {
        toaster.toast({ title: `Updating ${PLUGIN_NAME}`, body: `Downloading v${status.latest_version}...` });
        installPluginUpdate(status).then(
          (version) => toaster.toast({ title: `${PLUGIN_NAME} updated`, body: `v${version} installed, reloading` }),
          (error) => toaster.toast({ title: "Update failed", body: error instanceof Error ? error.message : String(error) }),
        );
      },
    });
  } catch {
    // Offline at boot: the Settings tab checks again when it opens.
  }
}
