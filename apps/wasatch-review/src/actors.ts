import type { ActorChoice } from "./types";

export const LABORATORY_ACTOR_HEADER = "X-Laboratory-Actor";

export interface LaboratoryActorOption {
  id: ActorChoice;
  label: string;
  detail: string;
}

export const LABORATORY_ACTORS: readonly LaboratoryActorOption[] = [
  {
    id: "emp_0001",
    label: "Jordan Hale",
    detail: "emp_0001, general manager, approver",
  },
  {
    id: "emp_0004",
    label: "Elena Voss",
    detail: "emp_0004, dispatcher, not an approver",
  },
  {
    id: "anonymous",
    label: "Anonymous",
    detail: "no actor header",
  },
];

export function actorHeaderValue(actor: ActorChoice): string | null {
  return actor === "anonymous" ? null : actor;
}
