#ifndef FINDBEATS_H
#define FINDBEATS_H

#include <string>
#include <cstdio>
#include <iostream>
#include <memory>
#include <stdexcept>
#include <string>
#include <array>
#include <thread>
#include <mutex>

#define MAX_LINE_LENGTH 256

class FindBeats {
public:
	FindBeats(const std::string& cmd, size_t onsetLengthMs = 200, bool verbose = true)
	: m_cmd(cmd), m_verbose(verbose), m_stop(false), m_lastOnsetTime(0), m_onsetLengthMs(onsetLengthMs)
	{}

	void start() {
		runProcess(m_cmd);
	}

	void runProcess(const std::string& cmd) {
	    std::shared_ptr<FILE> pipe(popen(cmd.c_str(), "r"), pclose);
	    if (!pipe)
	    	throw std::runtime_error("popen() failed!");

	    auto run = [=]() {
		    std::array<char, MAX_LINE_LENGTH> buffer;
		    std::cout << "FindBeats started\n";
		    while (fgets(buffer.data(), MAX_LINE_LENGTH, pipe.get()) != nullptr && !m_stop) {
	            std::string line = buffer.data();
	            // std::cout << "FindBeats output: " << line << std::endl;
	            // for (auto& c: line) {
	            // 	std::cout << (size_t)c << std::endl;
	            // }
	            // line must end in \n
	            assert(line.back() == 10);

	            line.erase(line.end() - 1);
            	setFromOnsetsString(line);
		    }
		    std::cout << "FindBeats terminated\n";
		};	
	    m_thread = std::thread(run);
	    m_thread.detach();
	}

	void stop() {
	    std::cout << "Stopping FindBeats\n";
	    m_stop = true;
	    if (m_thread.joinable()) {
	        m_thread.join();
	    }
	}   

	std::vector<bool> getOnsets() {
		std::vector<bool> onsets(m_onsets.size());
		m_mutex.lock();
		if (millis() - m_lastOnsetTime < m_onsetLengthMs)
			onsets = m_onsets;
		else
			for (bool onset: onsets)
				onset = false;
		m_mutex.unlock();
		return onsets;
	}

private:
	void setFromOnsetsString(const std::string& line) {
        if (line.size() == 0 || line[0] != '[' || line.back() != ']') {
        	if (m_verbose)
        		std::cerr << "Invalid onsets string: " << line << std::endl;
        	return;
        }

		std::vector<bool> onsets;
		for (size_t i = 1; i < line.size() - 1; ++i) {
			assert(line[i] == '0' || line[i] == '1');
			onsets.push_back(line[i] == '1');
		}

		m_mutex.lock();
		m_lastOnsetTime = millis();
		m_onsets = onsets;
		m_mutex.unlock();
		std::cout << line << std::endl;
	}

	std::string m_cmd;
	bool m_verbose;
	std::thread m_thread;
    std::mutex m_mutex;
    std::vector<bool> m_onsets;
    bool m_stop;
    unsigned long m_lastOnsetTime;
    size_t m_onsetLengthMs;
};

#endif
