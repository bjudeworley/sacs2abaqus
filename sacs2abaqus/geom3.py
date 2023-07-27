import math
from typing import Tuple


class Vector3:
    def __init__(self, x: float, y: float, z: float):
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def as_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)

    def normalise(self) -> "Vector3":
        return self / self.length()

    def length(self) -> float:
        return math.sqrt(self.dot(self))

    def dot(self, rhs: "Vector3") -> float:
        return self.x * rhs.x + self.y * rhs.y + self.z * rhs.z

    def cross(self, rhs: "Vector3") -> "Vector3":
        a1, a2, a3 = (self.x, self.y, self.z)
        b1, b2, b3 = (rhs.x, rhs.y, rhs.z)
        x = a2 * b3 - a3 * b2
        y = a3 * b1 - a1 * b3
        z = a1 * b2 - a2 * b1
        return Vector3(x, y, z)

    def __add__(self, rhs: "Vector3") -> "Vector3":
        if not isinstance(rhs, Vector3):
            return NotImplemented
        return Vector3(self.x + rhs.x, self.y + rhs.y, self.z + rhs.z)

    def __sub__(self, rhs: "Vector3") -> "Vector3":
        if not isinstance(rhs, Vector3):
            return NotImplemented
        return Vector3(self.x - rhs.x, self.y - rhs.y, self.z - rhs.z)

    def __mul__(self, rhs: float) -> "Vector3":
        if not (isinstance(rhs, float) or isinstance(rhs, int)):
            return NotImplemented
        return Vector3(self.x * rhs, self.y * rhs, self.z * rhs)

    def __rmul__(self, rhs: float) -> "Vector3":
        return self * rhs

    def __truediv__(self, rhs: float) -> "Vector3":
        if not (isinstance(rhs, float) or isinstance(rhs, int)):
            return NotImplemented
        return (1.0 / rhs) * self

    def __neg__(self) -> "Vector3":
        return Vector3(-self.x, -self.y, -self.z)

    def __eq__(self, rhs: "Vector3") -> bool:
        tol = 1e-6
        return isinstance(rhs, Vector3) and (
            abs(self.x - rhs.x) <= tol
            and abs(self.y - rhs.y) <= tol
            and abs(self.z - rhs.z) <= tol
        )


class BeamCSys:
    @staticmethod
    def from_sacs_points(start: Vector3, end: Vector3) -> "BeamCSys":
        tol = 1e-6
        vec = end - start
        x = vec.normalise()
        if abs(abs(x.z) - 1) <= tol:
            # Vertical beam: local Z is in global Y
            z = Vector3(0, 1, 0)
            y = z.cross(x).normalise()
        else:
            # Non-vertical beam: local Z is in the plane formed by the beam and the
            # global Z axis
            z = Vector3(0, 0, 1)
            y = z.cross(x).normalise()
            z = x.cross(y).normalise()
        return BeamCSys(x, y, z)

    def __init__(self, x: Vector3, y: Vector3, z: Vector3 = None):
        if z is None:
            z = x.cross(y)
        self.x = x.normalise()
        self.y = y.normalise()
        self.z = z.normalise()

    def rotated_about_x(self, angle: float) -> "BeamCSys":
        # Rotate the coordinate system around the X axis
        rad_ang = math.radians(angle)
        sin_theta = math.sin(rad_ang)
        cos_theta = math.cos(rad_ang)
        y = self.y * cos_theta + self.z * sin_theta
        z = self.z * cos_theta - self.y * sin_theta
        return BeamCSys(self.x, y, z)

    def __eq__(self, rhs: "BeamCSys") -> bool:
        if not isinstance(rhs, BeamCSys):
            return False
        return self.x == rhs.x and self.y == rhs.y and self.z == rhs.z
