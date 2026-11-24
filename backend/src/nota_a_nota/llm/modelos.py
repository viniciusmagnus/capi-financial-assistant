def raciocinio(modelo: str, pensar: bool, esforco: str | None = None) -> dict:
    parametros: dict = {}
    if not pensar:
        if "haiku" in modelo:
            parametros["thinking"] = {"type": "disabled"}
        elif "sonnet-5-5" in modelo:
            parametros["thinking"] = {"type": "between_tools"}
        else:
            esforco = esforco or "low"
    if esforco:
        parametros["output_config"] = {"effort": esforco}
    return parametros
