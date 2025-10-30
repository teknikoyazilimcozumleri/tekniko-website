import { defineCollection, z } from "astro:content";

const posts = defineCollection({
    schema: z.object({
        title: z.string(),
        image: z.string(),
        tags: z.array(z.string()),
        slug: z.string(),
        content: z.string(),
    }),
});

export const collections = {
    'posts': posts,
};