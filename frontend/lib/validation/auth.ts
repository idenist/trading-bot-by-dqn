import { z } from "zod";

export const loginSchema = z.object({
  email: z.string().email("이메일 형식이 아닙니다."),
  password: z.string().min(8, "비밀번호는 8자 이상"),
});
export type LoginInput = z.infer<typeof loginSchema>;

export const registerSchema = z.object({
  email: z.string().email("이메일 형식이 아닙니다."),
  password: z.string().min(8, "비밀번호는 8자 이상"),
  confirm: z.string(),
}).refine((d) => d.password === d.confirm, { path: ["confirm"], message: "비밀번호가 일치하지 않습니다." });
export type RegisterInput = z.infer<typeof registerSchema>;
