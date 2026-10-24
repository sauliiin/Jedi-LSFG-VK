export enum ConfigFieldType { BOOLEAN = "boolean", INTEGER = "integer", FLOAT = "float", STRING = "string", ARRAY = "array" }

export const DLL = "dll" as const;
export const NO_FP16 = "no_fp16" as const;
export const TARGET_FPS = "target_fps" as const;
export const FLOW_SCALE = "flow_scale" as const;
export const PERFORMANCE_MODE = "performance_mode" as const;
export const PRESERVE_SWAPCHAIN_IMAGE_COUNT = "preserve_swapchain_image_count" as const;

export const TARGET_FPS_MIN = 60;
export const TARGET_FPS_MAX = 120;

export interface ConfigField { name: string; fieldType: ConfigFieldType; default: boolean | number | string | string[]; description: string; }
export interface ConfigurationData {
  dll: string; no_fp16: boolean; target_fps: number;
  flow_scale: number; performance_mode: boolean; preserve_swapchain_image_count: boolean;
}
export const CONFIG_SCHEMA: Record<string, ConfigField> = {
  dll: { name: "dll", fieldType: ConfigFieldType.STRING, default: "", description: "Override the Lossless.dll path" },
  no_fp16: { name: "no_fp16", fieldType: ConfigFieldType.BOOLEAN, default: false, description: "Disable FP16 acceleration" },
  target_fps: { name: "target_fps", fieldType: ConfigFieldType.INTEGER, default: 60, description: "Adaptive frame generation target" },
  flow_scale: { name: "flow_scale", fieldType: ConfigFieldType.FLOAT, default: 0.8, description: "Motion estimation resolution scale" },
  performance_mode: { name: "performance_mode", fieldType: ConfigFieldType.BOOLEAN, default: true, description: "Use the lighter frame generation model" },
  preserve_swapchain_image_count: { name: "preserve_swapchain_image_count", fieldType: ConfigFieldType.BOOLEAN, default: false, description: "Preserve the swapchain image count" },
};
export function getFieldNames(): string[] { return Object.keys(CONFIG_SCHEMA); }
export function getDefaults(): ConfigurationData { return { dll: "", no_fp16: false, target_fps: 60, flow_scale: 0.8, performance_mode: true, preserve_swapchain_image_count: false }; }
export function getFieldTypes(): Record<string, ConfigFieldType> { return Object.fromEntries(Object.entries(CONFIG_SCHEMA).map(([key, value]) => [key, value.fieldType])); }
