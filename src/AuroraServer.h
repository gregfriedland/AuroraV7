#include <grpc/grpc.h>
#include <grpc++/server.h>
#include <grpc++/server_builder.h>
#include <grpc++/server_context.h>
#include <grpc++/security/server_credentials.h>
#include <Aurora.grpc.pb.h>
#include "Matrix.h"

using grpc::Server;
using grpc::ServerBuilder;
using grpc::ServerContext;
using grpc::ServerReader;
using grpc::ServerReaderWriter;
using grpc::ServerWriter;
using grpc::Status;
using namespace aurora;

class AuroraServer final : public Aurora::Service {
public:
	explicit AuroraServer(Matrix* matrix) : m_matrix(matrix) {
  	}

	Status SendFrame(ServerContext* context, const Frame* frame, Empty* empty) override {
	    //std::cout << "Receiving frame (" << frame->pixels().size() << ")" << std::endl;
	    m_matrix->update();

	    if (frame->pixels().size() != m_matrix->width() * m_matrix->height() * 3) {
	    	std::cerr << "Invalid # of frame pixels: " << frame->pixels().size() << std::endl;
		    return Status::CANCELLED;
	    }

		const char* buf = &frame->pixels()[0];
	    for (size_t y = 0; y < m_matrix->height(); y++) {
	        for (size_t x = 0; x < m_matrix->width(); x++) {
	            size_t index = (m_matrix->width() * y + x) * 3;
	            m_matrix->setPixel(x, y, buf[index], buf[index + 1], buf[index + 2]);
	        }
	    }

    return Status::OK;
  }

protected:
	Matrix* m_matrix;
};
