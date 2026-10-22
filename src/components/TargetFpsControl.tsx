import { Focusable, PanelSectionRow, SliderField } from "@decky/ui";
import { useEffect, useRef, useState } from "react";
import { ConfigurationData, TARGET_FPS, TARGET_FPS_MAX, TARGET_FPS_MIN } from "../config/configSchema";
import t from "../i18n/i18n";

interface TargetFpsControlProps {
  config: ConfigurationData;
  onConfigChange: (fieldName: keyof ConfigurationData, value: boolean | number | string | string[]) => Promise<void>;
  autoFocus?: boolean;
  onAutoFocus?: () => void;
}

// Every save rewrites and validates the profile, so dragging only commits
// the value the slider settles on.
const SAVE_DEBOUNCE_MS = 300;
const NOTCH_STEP = 30;
const NOTCH_COUNT = (TARGET_FPS_MAX - TARGET_FPS_MIN) / NOTCH_STEP + 1;
const NOTCH_LABELS = [30, 60, 90, 120, 180, 240].map((value) => ({
  notchIndex: (value - TARGET_FPS_MIN) / NOTCH_STEP,
  label: String(value),
  value,
}));

export function TargetFpsControl({
  config,
  onConfigChange,
  autoFocus = false,
  onAutoFocus,
}: TargetFpsControlProps) {
  const focusableRef = useRef<HTMLDivElement>(null);
  const timer = useRef<number | null>(null);
  const [pendingValue, setPendingValue] = useState<number | null>(null);
  const value = pendingValue ?? config.target_fps;

  useEffect(() => {
    if (!autoFocus) return;
    const frame = requestAnimationFrame(() => {
      const target = focusableRef.current?.querySelector<HTMLElement>(
        '[role="button"], [role="slider"]',
      );
      target?.focus();
      onAutoFocus?.();
    });
    return () => cancelAnimationFrame(frame);
  }, [autoFocus, onAutoFocus]);

  useEffect(() => () => {
    if (timer.current !== null) window.clearTimeout(timer.current);
  }, []);

  useEffect(() => {
    if (pendingValue === config.target_fps) setPendingValue(null);
  }, [config.target_fps, pendingValue]);

  const handleChange = (next: number) => {
    setPendingValue(next);
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      timer.current = null;
      void onConfigChange(TARGET_FPS, next);
    }, SAVE_DEBOUNCE_MS);
  };

  return (
    <PanelSectionRow>
      <Focusable ref={focusableRef} noFocusRing>
        <SliderField
          label={`${t("CONFIG_TARGET_FPS", "Target FPS")} · ${value}`}
          value={value}
          min={TARGET_FPS_MIN}
          max={TARGET_FPS_MAX}
          step={1}
          notchCount={NOTCH_COUNT}
          notchLabels={NOTCH_LABELS}
          notchTicksVisible={true}
          showValue={false}
          onChange={handleChange}
        />
      </Focusable>
    </PanelSectionRow>
  );
}
