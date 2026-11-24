import assert from "node:assert/strict";
import { test } from "node:test";

import { destinoSeguro, paginaDeEntrada } from "./destino.ts";

test("aceita caminhos internos e preserva a consulta", () => {
  assert.equal(destinoSeguro("/regras"), "/regras");
  assert.equal(destinoSeguro("/?mes=2026-10"), "/?mes=2026-10");
  assert.equal(destinoSeguro("/busca?q=comida%20fora"), "/busca?q=comida%20fora");
});

test("recusa destinos externos, ambíguos ou de outro esquema", () => {
  for (const ruim of [
    "https://atacante.example",
    "//atacante.example",
    "/\\atacante.example",
    "\\\\atacante.example",
    "javascript:alert(1)",
    "/%0d%0aLocation:https://x",
    "/\u0000",
    "regras",
    "",
    undefined,
    42,
    "/" + "a".repeat(600),
  ]) {
    assert.equal(destinoSeguro(ruim), "/", String(ruim));
  }
});

test("não volta para as próprias páginas de entrada nem para a API", () => {
  assert.equal(destinoSeguro("/entrar?volta=/regras"), "/");
  assert.equal(destinoSeguro("/redefinir-senha?token=x"), "/");
  assert.equal(destinoSeguro("/api/auth/sign-out"), "/");
});

test("monta a página de entrada só com destino seguro", () => {
  assert.equal(paginaDeEntrada("/regras"), "/entrar?volta=%2Fregras");
  assert.equal(paginaDeEntrada("https://x.example", { expirou: "1" }), "/entrar?expirou=1");
  assert.equal(paginaDeEntrada("/"), "/entrar");
});
