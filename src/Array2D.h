#ifndef ARRAY2D_H
#define ARRAY2D_H

template<typename T>
class Array2D {
 public:
 	Array2D(size_t width, size_t height)
 	: m_width(width), m_height(height) {
 		m_data = new T[width*height];
 	}

 	~Array2D() {
 		delete[] m_data;
 	}

 	T& get(int x, int y) {
		if (x < 0)
 			x += m_width;
 		else if (x >= m_width)
 			x -= m_width;

 		if (y < 0)
 			y += m_height;
 		else if (y >= m_height)
 			y -= m_height;

 		return m_data[x + y * m_width];
  	}

 	const T& get(int x, int y) const {
		if (x < 0)
 			x += m_width;
 		else if (x >= m_width)
 			x -= m_width;

 		if (y < 0)
 			y += m_height;
 		else if (y >= m_height)
 			y -= m_height;

 		return m_data[x + y * m_width];
  	}

 	T& get(size_t index) {
 		return m_data[index];
 	}

 	const T& get(size_t index) const {
 		return m_data[index];
 	}

 	T& operator[](size_t index) {
 		return m_data[index];
 	}

 	const T& operator[](size_t index) const {
 		return m_data[index];
 	}

 	void random() {
 		for (size_t x = 0; x < m_width; ++x) {
 			for (size_t y = 0; y < m_height; ++y) {
 				get(x, y) = (random2() % 10000) / 10000.0;
 			}
 		}
 	}

 	T sum() const {
 		T sum = 0;
 		for (size_t x = 0; x < m_width; ++x) {
 			for (size_t y = 0; y < m_height; ++y) {
 				sum += get(x, y);
 			}
 		}
 		return sum;
 	}

 	void constrain(T min, T max) {
 		for (size_t x = 0; x < m_width; ++x) {
 			for (size_t y = 0; y < m_height; ++y) {
 				get(x, y) = std::min(min, std::max(max, get(x, y)));
 			}
 		}
 	}

 	T* rawData() const {
 		return m_data;
 	}

 	size_t width() const {
 		return m_width;
 	}

 	size_t height() const {
 		return m_height;
 	}

	friend std::ostream& operator <<(std::ostream& os, const Array2D<T>& arr) {
		for (size_t y = 0; y < arr.m_height; ++y) {
	 		for (size_t x = 0; x < arr.m_width; ++x) {
	 			auto& val = arr.get(x, y);
 				os << std::setw(4) << std::round(val * 100) / 100 << " ";
 			}
 			os << std::endl;
 		}
 		return os;
	}
	
 protected:
 	size_t m_width, m_height;
 	T* m_data;
};

#ifdef __arm__
template <typename T, typename NEON_TYPE, int REGISTER_N>
class Array2DNeon {
 public:
 	Array2DNeon(size_t width, size_t height)
 	: m_width(width), m_height(height) {
            m_numVectors = width * height / REGISTER_N;
	    m_data = new NEON_TYPE[m_numVectors];
       }

 	~Array2DNeon() {
 		delete[] m_data;
 	}

 	T get(size_t index) const {
 		T out[REGISTER_N];
 		vst1q_f32(out, m_data[index / REGISTER_N]);
 		return out[index % REGISTER_N];
 	}

 	void set1(size_t index, T val) {
 		T tmp[REGISTER_N];
 		vst1q_f32(tmp, m_data[index / REGISTER_N]);
 		tmp[index % REGISTER_N] = val;
 		m_data[index / REGISTER_N] = vld1q_f32(tmp);
 	}

 	void setN(size_t index, T val) {
	  assert(index % REGISTER_N == 0);
	  m_data[index / REGISTER_N] = vdupq_n_f32(val);
 	}

 	void setN(size_t index, const NEON_TYPE& val) {
	  assert(index % REGISTER_N == 0);
	  m_data[index / REGISTER_N] = val;
 	}

	template <int REM, bool CHECK_BOUNDS = false>
 	NEON_TYPE getN(size_t index) const {
	  //asm (""); // to prevent inlining
	  if (REM == 0) {
	    return m_data[index / REGISTER_N];
	  } else {
	    size_t indexN = index / REGISTER_N;
	    size_t indexNextN = indexN + 1;
	    if (CHECK_BOUNDS) {
	      indexNextN %= m_numVectors;
	    }
	    
	    const NEON_TYPE& v1 = m_data[indexN];
	    const NEON_TYPE& v2 = m_data[indexNextN];
	    NEON_TYPE out;
	    if (REM == 1) {
	      out = vsetq_lane_f32(vgetq_lane_f32(v1, 1), out, 0);
	      out = vsetq_lane_f32(vgetq_lane_f32(v1, 2), out, 1);
	      out = vsetq_lane_f32(vgetq_lane_f32(v1, 3), out, 2);
	      out = vsetq_lane_f32(vgetq_lane_f32(v2, 0), out, 3);
	    } else if (REM == 2) {
	      out = vsetq_lane_f32(vgetq_lane_f32(v1, 2), out, 0);
	      out = vsetq_lane_f32(vgetq_lane_f32(v1, 3), out, 1);
	      out = vsetq_lane_f32(vgetq_lane_f32(v2, 0), out, 2);
	      out = vsetq_lane_f32(vgetq_lane_f32(v2, 1), out, 3);
	    } else if (REM == 3) {
	      out = vsetq_lane_f32(vgetq_lane_f32(v1, 3), out, 0);
	      out = vsetq_lane_f32(vgetq_lane_f32(v2, 0), out, 1);
	      out = vsetq_lane_f32(vgetq_lane_f32(v2, 1), out, 2);
	      out = vsetq_lane_f32(vgetq_lane_f32(v2, 2), out, 3);
	    }
	    return out;
	  }
	}

#if 0	    
	template <bool CHECK_BOUNDS = false>
 	NEON_TYPE getN(size_t index) const {
	  size_t remainder = index % REGISTER_N;
	  if (remainder == 0) {
	    return m_data[index / REGISTER_N];
	  }

	  size_t indexN = index / REGISTER_N;
	  size_t indexNextN;
	  if (CHECK_BOUNDS) {
	    indexNextN = (indexN + 1) % m_numVectors;
	  } else {
	    indexNextN = indexN + 1;
	  }

	  const NEON_TYPE& v1 = m_data[indexN];
	  const NEON_TYPE& v2 = m_data[indexNextN];
	  NEON_TYPE out;
	  switch (remainder) {
	  case 1:
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 1), out, 0);
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 2), out, 1);
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 3), out, 2);
	    out = vsetq_lane_f32(vgetq_lane_f32(v2, 0), out, 3);
	    break;
	  case 2:
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 2), out, 0);
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 3), out, 1);
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 0), out, 2);
	    out = vsetq_lane_f32(vgetq_lane_f32(v2, 1), out, 3);
	    break;
	  case 3:
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 3), out, 0);
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 0), out, 1);
	    out = vsetq_lane_f32(vgetq_lane_f32(v1, 1), out, 2);
	    out = vsetq_lane_f32(vgetq_lane_f32(v2, 2), out, 3);
	    break;
	  }
	  return out;
	}
#endif
 	size_t width() const {
 		return m_width;
 	}

 	size_t height() const {
 		return m_height;
 	}

	friend std::ostream& operator <<(std::ostream& os, const Array2DNeon<T,NEON_TYPE,REGISTER_N>& arr) {
	  for (size_t y = 0; y < arr.m_height; ++y) {
	    for (size_t x = 0; x < arr.m_width; ++x) {
	      size_t i = x + y * arr.m_width;
	      os << std::setw(4) << std::round(arr.get(i) * 100.0) / 100.0 << " ";
	    }
	    os << std::endl;
	  }
	  return os;
	}

 protected:
 	size_t m_width, m_height;
 	NEON_TYPE* m_data;
	size_t m_numVectors;
};

#endif
#endif
