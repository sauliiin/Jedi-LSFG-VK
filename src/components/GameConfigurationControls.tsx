import { ConfigurationData } from "../config/configSchema";
import type { GameTarget } from "../hooks/useGameConfiguration";
import { ConfigurationSection } from "./ConfigurationSection";
import { TargetFpsControl } from "./TargetFpsControl";
import { WorkaroundsSection } from "./WorkaroundsSection";

interface Props {
  config: ConfigurationData;
  onConfigChange: (fieldName: keyof ConfigurationData, value: boolean | number | string | string[]) => Promise<void>;
  autoFocusTargetFps?: boolean;
  onTargetFpsFocused?: () => void;
  showWorkarounds?: boolean;
  workaroundTarget?: Pick<GameTarget, "appid" | "nonSteam">;
  onRepairWorkaround?: () => Promise<boolean>;
}

export function GameConfigurationControls({
  config,
  onConfigChange,
  autoFocusTargetFps,
  onTargetFpsFocused,
  showWorkarounds = false,
  workaroundTarget,
  onRepairWorkaround,
}: Props) {
  return (
    <>
      <TargetFpsControl
        config={config}
        onConfigChange={onConfigChange}
        autoFocus={autoFocusTargetFps}
        onAutoFocus={onTargetFpsFocused}
      />
      <ConfigurationSection config={config} onConfigChange={onConfigChange} />
      {showWorkarounds && workaroundTarget && (
        <WorkaroundsSection
          appId={workaroundTarget.appid}
          nonSteam={workaroundTarget.nonSteam}
          onRepair={onRepairWorkaround}
        />
      )}
    </>
  );
}
