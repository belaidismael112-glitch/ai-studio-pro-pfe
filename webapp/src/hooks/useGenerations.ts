import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { generationApi } from '@/lib/api';
import { Generation, ImageGenerationRequest } from '@/types';

export function useGenerations(params?: {
  generation_type?: string;
  status?: string;
  page?: number;
  page_size?: number;
}) {
  return useQuery({
    queryKey: ['generations', params],
    queryFn: async () => {
      const response = await generationApi.getGenerations(params);
      return response.data;
    },
  });
}

export function useGenerateImage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (data: ImageGenerationRequest) => {
      const response = await generationApi.generateImage(data);
      return response.data as Generation;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['generations'] });
      queryClient.invalidateQueries({ queryKey: ['user'] });
    },
  });
}


export function useDeleteGeneration() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (id: number) => {
      await generationApi.deleteGeneration(id);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['generations'] });
    },
  });
}
