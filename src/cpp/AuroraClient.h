#include <grpc/grpc.h>
#include <grpc++/channel.h>
#include <grpc++/client_context.h>
#include <grpc++/create_channel.h>
#include <grpc++/security/credentials.h>
#include <Aurora.grpc.pb.h>
#include "Matrix.h"

using grpc::Channel;
using grpc::ClientContext;
using grpc::ClientReader;
using grpc::ClientReaderWriter;
using grpc::ClientWriter;
using grpc::Status;
using namespace aurora;

class AuroraClient {
public:
	AuroraClient(std::shared_ptr<Channel> channel) : m_stub(Aurora::NewStub(channel)) {
	}

	bool sendFrame(const std::string& data) {
		Frame frame;
		frame.set_pixels(&data[0]);
		Empty empty;

  		ClientContext context;
    	Status status = m_stub->SendFrame(&context, frame, &empty);
    
    	if (!status.ok()) {
      		std::cout << "SendFrame rpc failed." << std::endl;
      		return false;
    	}

    	return true;
	}

protected:
	std::unique_ptr<Aurora::Stub> m_stub;	
};
