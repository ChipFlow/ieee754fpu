import math


def run_cordic(z0, fracbits=8, log=True):
    M = 1<<fracbits
    N = fracbits+1
    An = 1.0
    for i in range(N):
        An *= math.sqrt(1 + 2**(-2*i))

    X0 = int(round(M*1/An))

    x = X0
    y = 0
    z = z0
    angles = tuple([int(round(M*math.atan(2**(-i)))) for i in range(N)])

    for i in range(N):
        dx = y >> i
        dy = x >> i
        dz = angles[i]


        if z >= 0:
            x -= dx
            y += dy
            z -= dz
        else:
            x += dx
            y -= dy
            z += dz
        if log:
            print("iteration {}".format(i))
            print("dx: {}, dy: {}, dz: {}".format(dx, dy, dz))
            print("x: {}, y: {}, z: {}".format(x, y, z))
    return (y, x)
