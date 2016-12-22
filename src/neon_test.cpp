
int main(int argc, char** argv) {
	__fp16 u[128];

	for (size_t i = 0; i < 128; i += 8) {
	    float16x8_t u_n8 = vld1q_f16(u + i);
	    float16x8_t uu_n8 = vmulq_f16(u_n8, u_n8);
	}
}
