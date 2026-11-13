import { useQuery } from "@tanstack/react-query";
import { listProviders } from "../api";

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => listProviders(true),
    staleTime: 60000,
    retry: 1,
  });
}
