import "server-only";

import { betterAuth } from "better-auth";
import { APIError, createAuthMiddleware } from "better-auth/api";
import { nextCookies } from "better-auth/next-js";
import { haveIBeenPwned, jwt } from "better-auth/plugins";
import { Pool } from "pg";

import { emailContaExistente, emailRecuperacao, emailSenhaTrocada, emailVerificacao } from "@/lib/email";

const URL_BASE = (process.env.BETTER_AUTH_URL ?? "http://localhost:3100").replace(/\/$/, "");
const EM_HTTPS = URL_BASE.startsWith("https://");
const MINUTO = 60;
const HORA = 60 * MINUTO;
const DIA = 24 * HORA;
const MARCA_DE_LINK_USADO = "verificacao-usada:";

export const AUDIENCIA_DA_API = process.env.AUTH_AUDIENCE ?? "nota-a-nota-api";
export const autenticacaoConfigurada = Boolean(process.env.BETTER_AUTH_SECRET && process.env.DATABASE_URL);
export const googleConfigurado = Boolean(process.env.GOOGLE_CLIENT_ID && process.env.GOOGLE_CLIENT_SECRET);
export const TAMANHO_MINIMO_DA_SENHA = 12;
export const TAMANHO_MAXIMO_DA_SENHA = 256;

const globais = globalThis as unknown as { poolDaAutenticacao?: Pool };
const pool = (globais.poolDaAutenticacao ??= new Pool({ connectionString: process.env.DATABASE_URL, max: 5 }));

function lista(valor: string | undefined) {
  return (valor ?? "")
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

const verificacaoDeUsoUnico = {
  antes: createAuthMiddleware(async (ctx) => {
    if (ctx.path === "/token" && ctx.request) {
      throw new APIError("NOT_FOUND");
    }
    if (ctx.path !== "/verify-email") return;
    const token = typeof ctx.query?.token === "string" ? ctx.query.token : "";
    if (token && (await ctx.context.internalAdapter.findVerificationValue(MARCA_DE_LINK_USADO + token))) {
      throw ctx.redirect(`${URL_BASE}/verificar-email?error=LINK_USADO`);
    }
  }),
  depois: createAuthMiddleware(async (ctx) => {
    if (ctx.path !== "/verify-email") return;
    const token = typeof ctx.query?.token === "string" ? ctx.query.token : "";
    if (!token) return;
    await ctx.context.internalAdapter.createVerificationValue({
      identifier: MARCA_DE_LINK_USADO + token,
      value: "1",
      expiresAt: new Date(Date.now() + (DIA + HORA) * 1000),
    });
  }),
};

export const auth = betterAuth({
  appName: "Capi",
  baseURL: URL_BASE,
  secret: process.env.BETTER_AUTH_SECRET,
  database: pool,
  trustedOrigins: [URL_BASE],
  emailAndPassword: {
    enabled: true,
    requireEmailVerification: true,
    autoSignIn: false,
    minPasswordLength: TAMANHO_MINIMO_DA_SENHA,
    maxPasswordLength: TAMANHO_MAXIMO_DA_SENHA,
    resetPasswordTokenExpiresIn: 30 * MINUTO,
    revokeSessionsOnPasswordReset: true,
    sendResetPassword: async ({ user, url }) => {
      await emailRecuperacao(user.email, user.name, url);
    },
    onExistingUserSignUp: async ({ user }) => {
      await emailContaExistente(user.email, user.name, `${URL_BASE}/entrar`, `${URL_BASE}/recuperar-senha`);
    },
    onPasswordReset: async ({ user }) => {
      await emailSenhaTrocada(user.email, user.name);
    },
  },
  emailVerification: {
    sendOnSignUp: true,
    sendOnSignIn: true,
    autoSignInAfterVerification: false,
    expiresIn: DIA,
    sendVerificationEmail: async ({ user, url }) => {
      const link = new URL(url);
      link.searchParams.set("callbackURL", "/verificar-email?confirmado=1");
      await emailVerificacao(user.email, user.name, link.toString());
    },
  },
  socialProviders: googleConfigurado
    ? {
        google: {
          clientId: process.env.GOOGLE_CLIENT_ID as string,
          clientSecret: process.env.GOOGLE_CLIENT_SECRET as string,
          redirectURI: `${URL_BASE}/api/auth/callback/google`,
          scope: ["openid", "email", "profile"],
          prompt: "select_account",
        },
      }
    : {},
  account: {
    encryptOAuthTokens: true,
    accountLinking: {
      enabled: true,
      disableImplicitLinking: true,
      allowDifferentEmails: false,
      trustedProviders: [],
    },
  },
  session: {
    expiresIn: 7 * DIA,
    updateAge: DIA,
    freshAge: 10 * MINUTO,
    cookieCache: { enabled: false },
  },
  verification: { storeIdentifier: "hashed" },
  rateLimit: {
    enabled: true,
    storage: "database",
    window: MINUTO,
    max: 100,
    customRules: {
      "/sign-in/email": { window: 5 * MINUTO, max: 8 },
      "/sign-up/email": { window: HORA, max: 5 },
      "/request-password-reset": { window: HORA, max: 5 },
      "/reset-password": { window: 15 * MINUTO, max: 10 },
      "/reset-password/*": false,
      "/send-verification-email": { window: HORA, max: 5 },
      "/sign-in/social": { window: 5 * MINUTO, max: 20 },
      "/change-password": { window: 15 * MINUTO, max: 5 },
    },
  },
  advanced: {
    cookiePrefix: "capi",
    useSecureCookies: EM_HTTPS,
    defaultCookieAttributes: { httpOnly: true, sameSite: "lax", secure: EM_HTTPS },
    ipAddress: {
      ipAddressHeaders: lista(process.env.AUTH_IP_HEADERS).length ? lista(process.env.AUTH_IP_HEADERS) : undefined,
      trustedProxies: lista(process.env.AUTH_TRUSTED_PROXIES),
    },
  },
  hooks: { before: verificacaoDeUsoUnico.antes, after: verificacaoDeUsoUnico.depois },
  plugins: [
    jwt({
      disableSettingJwtHeader: true,
      jwks: { keyPairConfig: { alg: "EdDSA", crv: "Ed25519" } },
      jwt: {
        issuer: URL_BASE,
        audience: AUDIENCIA_DA_API,
        expirationTime: "5m",
        definePayload: ({ user }) => ({ email_verified: user.emailVerified }),
      },
    }),
    ...(process.env.VERIFICAR_SENHA_VAZADA === "false"
      ? []
      : [haveIBeenPwned({ customPasswordCompromisedMessage: "Essa senha já apareceu em vazamentos públicos. Escolha outra." })]),
    nextCookies(),
  ],
});
