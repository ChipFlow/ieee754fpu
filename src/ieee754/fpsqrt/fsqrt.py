from sfpy import Float32


# XXX DO NOT USE, fails on num=65536.  wark-wark...
def sqrtsimple(num):
    res = 0
    bit = 1

    while (bit < num):
        bit <<= 2

    while (bit != 0):
        if (num >= res + bit):
            num -= res + bit
            res = (res >> 1) + bit
        else:
            res >>= 1
        bit >>= 2

    return res


def sqrt(num):
    D = num # D is input (from num)
    Q = 0 # quotient
    R = 0 # remainder
    for i in range(64, -1, -1): # negative ranges are weird...

        R = (R<<2)|((D>>(i+i))&3)

        if R >= 0:
            R -= ((Q<<2)|1) # -Q01
        else:
            R += ((Q<<2)|3) # +Q11

        Q <<= 1
        if R >= 0:
            Q |= 1 # new Q

    if R < 0:
        R = R + ((Q<<1)|1)

    return Q, R


# grabbed these from unit_test_single (convenience, this is just experimenting)

def get_mantissa(x):
    return 0x7fffff & x

def get_exponent(x):
    return ((x & 0x7f800000) >> 23) - 127

def set_exponent(x, e):
    return (x & ~0x7f800000) | ((e+127) << 23)

def get_sign(x):
    return ((x & 0x80000000) >> 31)

# convert FP32 to s/e/m
def create_fp32(s, e, m):
    """ receive sign, exponent, mantissa, return FP32 """
    return set_exponent((s << 31) | get_mantissa(m))

# convert s/e/m to FP32
def decode_fp32(x):
    """ receive FP32, return sign, exponent, mantissa """
    return get_sign(x), get_exponent(x), get_mantissa(x)


# main function, takes mantissa and exponent as separate arguments
# returns a tuple, sqrt'd mantissa, sqrt'd exponent

def main(mantissa, exponent):
    if exponent & 1 != 0:
        # shift mantissa up, subtract 1 from exp to compensate
        mantissa <<= 1
        exponent -= 1
    m, r = sqrt(mantissa)
    return m, r, exponent >> 1


#normalization function
def normalise(s, m, e, lowbits):
    if (lowbits >= 2):
        m += 1
    if get_mantissa(m) == ((1<<24)-1):
        e += 1

    # this is 2nd-stage normalisation.  can move it to a separate fn.

    #if the num is NaN, then adjust (normalised NaN rather than de-normed NaN)
    if (e == 128 & m !=0):
        # these are in IEEE754 format, this function returns s,e,m not z
        s = 1           # sign (so, s=1)
        e = 128         # exponent (minus 127, so e = 128
        m = 1<<22     # high bit of mantissa, so m = 1<<22 i think

    #if the num is Inf, then adjust (to normalised +/-INF)
    if (e == 128):
        # these are in IEEE754 format, this function returns s,e,m not z
        s = 1       # s is already s, so do nothing to s.
        e = 128  # have to subtract 127, so e = 128 (again)
        m = 0     # mantissa... so m=0

    return s, m, e


def fsqrt_test(x):

    xbits = x.bits
    print ("x", x, type(x))
    sq_test = x.sqrt()
    print ("sqrt", sq_test)

    print (xbits, type(xbits))
    s, e, m = decode_fp32(xbits)
    print("x decode", s, e, m, hex(m))

    m |= 1<<23 # set top bit (the missing "1" from mantissa)
    m <<= 27

    sm, sr, se = main(m, e)
    lowbits = sm & 0x3
    sm >>= 2
    sm = get_mantissa(sm)
    #sm += 2

    s, sm, se = normalise(s, sm, se, lowbits)

    print("our  sqrt", s, se, sm, hex(sm), bin(sm), "lowbits", lowbits,
                                                    "rem", hex(sr))
    if lowbits >= 2:
        print ("probably needs rounding (+1 on mantissa)")

    sq_xbits = sq_test.bits
    s, e, m = decode_fp32(sq_xbits)
    print ("sf32 sqrt", s, e, m, hex(m), bin(m))
    print ()

if __name__ == '__main__':

    # quick test up to 1000 of two sqrt functions
    for Q in range(1, int(1e4)):
        print(Q, sqrt(Q), sqrtsimple(Q), int(Q**0.5))
        assert int(Q**0.5) == sqrtsimple(Q), "Q sqrtsimpl fail %d" % Q
        assert int(Q**0.5) == sqrt(Q)[0], "Q sqrt fail %d" % Q

    # quick mantissa/exponent demo
    for e in range(26):
        for m in range(26):
            ms, mr, es = main(m, e)
            print("m:%d e:%d sqrt: m:%d-%d e:%d" % (m, e, ms, mr, es))

    x = Float32(1234.123456789)
    fsqrt_test(x)
    x = Float32(32.1)
    fsqrt_test(x)
    x = Float32(16.0)
    fsqrt_test(x)
    x = Float32(8.0)
    fsqrt_test(x)
    x = Float32(8.5)
    fsqrt_test(x)
    x = Float32(3.14159265358979323)
    fsqrt_test(x)
    x = Float32(12.99392923123123)
    fsqrt_test(x)
    x = Float32(0.123456)
    fsqrt_test(x)




"""

Notes:
https://pdfs.semanticscholar.org/5060/4e9aff0e37089c4ab9a376c3f35761ffe28b.pdf

//This is the main code of integer sqrt function found here:http://verilogcodes.blogspot.com/2017/11/a-verilog-function-for-finding-square-root.html
//

module testbench;

reg [15:0] sqr;

//Verilog function to find square root of a 32 bit number.
//The output is 16 bit.
function [15:0] sqrt;
    input [31:0] num;  //declare input
    //intermediate signals.
    reg [31:0] a;
    reg [15:0] q;
    reg [17:0] left,right,r;
    integer i;
begin
    //initialize all the variables.
    a = num;
    q = 0;
    i = 0;
    left = 0;   //input to adder/sub
    right = 0;  //input to adder/sub
    r = 0;  //remainder
    //run the calculations for 16 iterations.
    for(i=0;i<16;i=i+1) begin
        right = {q,r[17],1'b1};
        left = {r[15:0],a[31:30]};
        a = {a[29:0],2'b00};    //left shift by 2 bits.
        if (r[17] == 1) //add if r is negative
            r = left + right;
        else    //subtract if r is positive
            r = left - right;
        q = {q[14:0],!r[17]};
    end
    sqrt = q;   //final assignment of output.
end
endfunction //end of Function


c version (from paper linked from URL)

unsigned squart(D, r) /*Non-Restoring sqrt*/
    unsigned D; /*D:32-bit unsigned integer to be square rooted */
    int *r;
{
    unsigned Q = 0; /*Q:16-bit unsigned integer (root)*/
    int R = 0; /*R:17-bit integer (remainder)*/
    int i;
    for (i = 15;i>=0;i--) /*for each root bit*/
    {
        if (R>=0)
        { /*new remainder:*/
            R = R<<2)|((D>>(i+i))&3);
            R = R-((Q<<2)|1); /*-Q01*/
        }
        else
        { /*new remainder:*/
            R = R<<2)|((D>>(i+i))&3);
            R = R+((Q<<2)|3); /*+Q11*/
        }
        if (R>=0) Q = Q<<1)|1; /*new Q:*/
        else Q = Q<<1)|0; /*new Q:*/
    }

    /*remainder adjusting*/
    if (R<0) R = R+((Q<<1)|1);
    *r = R; /*return remainder*/
    return(Q); /*return root*/
}

From wikipedia page:

short isqrt(short num) {
    short res = 0;
    short bit = 1 << 14; // The second-to-top bit is set: 1 << 30 for 32 bits

    // "bit" starts at the highest power of four <= the argument.
    while (bit > num)
        bit >>= 2;

    while (bit != 0) {
        if (num >= res + bit) {
            num -= res + bit;
            res = (res >> 1) + bit;
        }
        else
            res >>= 1;
        bit >>= 2;
    }
    return res;
}

"""
