from nota_a_nota.llm.modelos import raciocinio


def test_cada_familia_desliga_o_raciocinio_do_jeito_que_aceita():
    assert raciocinio("claude-haiku-5-5", pensar=False) == {"thinking": {"type": "disabled"}}
    assert raciocinio("claude-sonnet-5-5", pensar=False) == {"thinking": {"type": "between_tools"}}
    assert raciocinio("claude-opus-5-5", pensar=False) == {"output_config": {"effort": "low"}}
    assert raciocinio("claude-fable-5-2", pensar=False) == {"output_config": {"effort": "low"}}


def test_com_raciocinio_so_ajusta_o_esforco():
    assert raciocinio("claude-opus-5-5", pensar=True) == {}
    assert raciocinio("claude-sonnet-5-5", pensar=True, esforco="medium") == {
        "output_config": {"effort": "medium"}
    }
