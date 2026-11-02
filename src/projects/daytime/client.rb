#!/usr/bin/env ruby
require 'socket'
require 'optparse'
require 'timeout'

options = { port: 13 }
parser = OptionParser.new do |opts|
  opts.banner = 'Usage: ruby client.rb (--tcp|-t|--udp|-u) [-p PORT] SERVER'
  opts.on('-t', '--tcp', 'Use TCP') do
    raise OptionParser::InvalidArgument, 'choose one protocol' if options[:protocol]
    options[:protocol] = :tcp
  end
  opts.on('-u', '--udp', 'Use UDP') do
    raise OptionParser::InvalidArgument, 'choose one protocol' if options[:protocol]
    options[:protocol] = :udp
  end
  opts.on('-p PORT', '--port PORT', Integer, 'Port (default: 13)') { |v| options[:port] = v }
  opts.on('-h', '--help', 'Show help') { puts opts; exit }
end

begin
  parser.parse!
  raise OptionParser::MissingArgument, 'choose --tcp or --udp' unless options[:protocol]
  raise OptionParser::InvalidArgument, 'provide exactly one server' unless ARGV.length == 1
  raise OptionParser::InvalidArgument, 'port must be 1..65535' unless (1..65535).cover?(options[:port])

  # RFC 867 does not prescribe a date format, so display the ASCII reply as received.
  response = Timeout.timeout(5) do
    socket = nil
    begin
      if options[:protocol] == :tcp
        socket = TCPSocket.new(ARGV.first, options[:port])
        socket.read
      else
        socket = UDPSocket.new
        socket.connect(ARGV.first, options[:port])
        socket.send("\n", 0)
        socket.recv(65_535)
      end
    ensure
      socket.close if socket
    end
  end
  raise IOError, 'server returned an empty response' if response.empty?
  STDOUT.write(response)
rescue OptionParser::ParseError => e
  warn "Error: #{e.message}"
  warn parser
  exit 1
rescue Timeout::Error
  warn 'Error: server did not complete the request within 5 seconds'
  exit 1
rescue SocketError, SystemCallError, IOError => e
  warn "Error: #{e.message}"
  exit 1
end
