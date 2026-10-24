import { toaster } from "@decky/api";
import { getPluginUpdateStatus, type PluginUpdateStatus } from "../api/lsfgApi";

// Decky's install type for replacing an installed plugin with a newer version.
const DECKY_INSTALL_TYPE_UPDATE = 2;
const PLUGIN_NAME = "Jedi LSFG-VK";

interface DeckyBackend {
  call?: (route: string, ...args: unknown[]) => Promise<unknown>;
}

/**
 * Hands the release ZIP to Decky's own installer. Decky asks to confirm,
 * checks the SHA-256, installs it and reloads the plugin.
 */
export async function installPluginUpdate(status: PluginUpdateStatus): Promise<void> {
  const backend = (window as unknown as { DeckyBackend?: DeckyBackend }).DeckyBackend;
  if (!status.url || !status.latest_version) throw new Error("No update is available");
  if (typeof backend?.call !== "function") {
    throw new Error(`This Decky Loader cannot install updates from plugins. Install from URL in Decky's settings: ${status.url}`);
  }
  await backend.call(
    "utilities/install_plugin",
    status.url,
    status.plugin_name || PLUGIN_NAME,
    status.latest_version,
    status.sha256 || "",
    DECKY_INSTALL_TYPE_UPDATE,
  );
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
        installPluginUpdate(status).catch((error) => {
          toaster.toast({ title: "Update failed", body: error instanceof Error ? error.message : String(error) });
        });
      },
    });
  } catch {
    // Offline at boot: the Settings tab checks again when it opens.
  }
}
