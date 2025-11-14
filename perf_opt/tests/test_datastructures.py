from perf_opt.datastructures import pack_price_year_flags, unpack_price_year_flags, bytes_from_ints, zero_copy_bytes_view


def test_bit_pack_roundtrip():
    p, y, n = 123456789, 1399, 1
    v = pack_price_year_flags(p, y, n)
    p2, y2, n2 = unpack_price_year_flags(v)
    assert p2 == p and y2 == y and n2 == n


def test_memoryview_zero_copy():
    buf = bytes_from_ints(range(10))
    mv = zero_copy_bytes_view(buf)
    assert len(mv) == len(buf)
    # Mutate through memoryview and see original changes
    mv[0] = 255
    assert buf[0] == 255

