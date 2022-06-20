from sgf_analyzer.utils import convert_position, parse_position


def test_convert_position_valid():
    assert convert_position(19, 'aa') == 'A19'
    assert convert_position(19, 'as') == 'A1'
    assert convert_position(19, 'sa') == 'T19'
    assert convert_position(19, 'ss') == 'T1'
    assert convert_position(19, 'jj') == 'K10'
    assert convert_position(19, '') == 'pass'

    assert convert_position(13, 'aa') == 'A13'
    assert convert_position(13, 'am') == 'A1'
    assert convert_position(13, 'ma') == 'N13'
    assert convert_position(13, 'mm') == 'N1'
    assert convert_position(13, 'gg') == 'G7'
    assert convert_position(13, '') == 'pass'

    assert convert_position(9, 'aa') == 'A9'
    assert convert_position(9, 'ai') == 'A1'
    assert convert_position(9, 'ia') == 'J9'
    assert convert_position(9, 'ii') == 'J1'
    assert convert_position(9, 'ee') == 'E5'
    assert convert_position(9, '') == 'pass'


def test_parse_position_valid():
    assert parse_position(19, 'A19') == 'aa'
    assert parse_position(19, 'A1') == 'as'
    assert parse_position(19, 'T19') == 'sa'
    assert parse_position(19, 'T1') == 'ss'
    assert parse_position(19, 'K10') == 'jj'
    assert parse_position(19, 'pass') == ''

    assert parse_position(13, 'A13') == 'aa'
    assert parse_position(13, 'A1') == 'am'
    assert parse_position(13, 'N13') == 'ma'
    assert parse_position(13, 'N1') == 'mm'
    assert parse_position(13, 'G7') == 'gg'
    assert parse_position(13, 'pass') == ''

    assert parse_position(9, 'A9') == 'aa'
    assert parse_position(9, 'A1') == 'ai'
    assert parse_position(9, 'J9') == 'ia'
    assert parse_position(9, 'J1') == 'ii'
    assert parse_position(9, 'E5') == 'ee'
    assert parse_position(9, 'pass') == ''
