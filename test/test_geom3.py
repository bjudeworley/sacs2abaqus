import pytest

from sacs2abaqus.geom3 import Vector3, BeamCSys


def test_vector3_cmp():
    assert Vector3(1, 2, 3) == Vector3(1, 2, 3)
    assert Vector3(1, 2, 3) != Vector3(1, 1, 3)

def test_vector3_conversion():
    assert Vector3(1, 2, 3).as_tuple() == (1, 2, 3)

def test_vector3_ops():
    a = Vector3(1, 2, 3)
    b = Vector3(2, -1, 5)
    assert a + b == Vector3(3, 1, 8)
    assert a - b == Vector3(-1, 3, -2)
    assert 2 * a == Vector3(2, 4, 6)
    assert a * 2 == Vector3(2, 4, 6)
    assert a / 2 == Vector3(0.5, 1, 1.5)


def test_vector3_length():
    assert Vector3(2, 6, 9).length() == 11


def test_vector3_normalise():
    assert Vector3(2, 6, 9).normalise() == Vector3(2 / 11, 6 / 11, 9 / 11)

def test_vector3_dot():
    assert Vector3(1, -3, 5).dot(Vector3(2, 3, -4)) == -27


def test_vector3_cross():
    a = Vector3(2, 0, 0)
    b = Vector3(0, 5, 0)
    c = Vector3(0, 0, 3)
    assert a.cross(b) == Vector3(0, 0, 10)
    assert b.cross(a) == Vector3(0, 0, -10)
    assert a.cross(c) == Vector3(0, -6, 0)
    assert b.cross(c) == Vector3(15, 0, 0)

def test_beamcsys_eq():
    a = BeamCSys(Vector3(1, 0, 0), Vector3(0, 2, 0), Vector3(0, 0, 0.1))
    b = BeamCSys(Vector3(2, 0, 0), Vector3(0, 1, 0))
    c = BeamCSys(Vector3(2, 0, 0), Vector3(0, -1, 0), Vector3(0, 0, -1))
    assert a == b
    assert a != c

def test_beamcsys_rotate():
    a = BeamCSys(Vector3(1, 0, 0), Vector3(0, 1, 0), Vector3(0, 0, 1))
    b = BeamCSys(Vector3(1, 0, 0), Vector3(0, 1, 1), Vector3(0, -1, 1))
    c = BeamCSys(Vector3(1, 0, 0), Vector3(0, 0, 1), Vector3(0, -1, 0))
    assert a.rotated_about_x(45) == b
    assert a.rotated_about_x(90) == c
