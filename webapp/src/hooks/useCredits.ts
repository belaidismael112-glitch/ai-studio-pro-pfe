import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { creditsApi } from '@/lib/api';
import { CreditPackage, CreditTransaction } from '@/types';

export function useCreditBalance() {
  return useQuery({
    queryKey: ['creditBalance'],
    queryFn: async () => {
      const response = await creditsApi.getBalance();
      return response.data;
    },
  });
}

export function useCreditPackages() {
  return useQuery({
    queryKey: ['creditPackages'],
    queryFn: async () => {
      const response = await creditsApi.getPackages();
      return response.data as CreditPackage[];
    },
  });
}

export function useCreditHistory(limit?: number) {
  return useQuery({
    queryKey: ['creditHistory', limit],
    queryFn: async () => {
      const response = await creditsApi.getHistory(limit);
      return response.data as CreditTransaction[];
    },
  });
}

export function usePurchaseCredits() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (packageId: string) => {
      const response = await creditsApi.purchase(packageId);
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['creditBalance'] });
      queryClient.invalidateQueries({ queryKey: ['creditHistory'] });
    },
  });
}
