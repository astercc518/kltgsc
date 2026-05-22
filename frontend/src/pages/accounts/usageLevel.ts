// Mirrors backend/app/core/account_roles.py — keep both in sync.
export const USAGE_LEVELS = [
  { value: 1, label: "等级 1 — 高危操作（群发/采集/拉群）", color: "red" },
  { value: 2, label: "等级 2 — 监听引流", color: "blue" },
  { value: 3, label: "等级 3 — 客服交流", color: "green" },
] as const;

export type UsageLevel = 1 | 2 | 3;

export const labelForUsageLevel = (level: number | null | undefined): string => {
  const entry = USAGE_LEVELS.find(u => u.value === level);
  return entry ? entry.label : "未指定";
};

export const colorForUsageLevel = (level: number | null | undefined): string => {
  const entry = USAGE_LEVELS.find(u => u.value === level);
  return entry ? entry.color : "default";
};
