#include <arm_neon.h>

int main(int argc, char** argv) {
	float u[128];
	for (int i = 0; i < 128; i += 8) {
	    float32x4_t u_n4 = vld1q_f32(u + i);
	    float32x4_t uu_n4 = vmulq_f32(u_n4, u_n4);
	}

	__fp16 u[128];
	for (int i = 0; i < 128; i += 8) {
	    float16x8_t u_n8 = vld1q_f16(u + i);
	    float16x8_t uu_n8 = vmulq_f16(u_n8, u_n8);
	}
}
