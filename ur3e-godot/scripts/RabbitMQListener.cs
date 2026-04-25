using System;
using System.Collections.Generic;
using System.Text;
using Godot;
using RabbitMQ.Client;
using RabbitMQ.Client.Events;

public partial class RabbitMQListener : Node
{
	private ConnectionFactory factory = new ConnectionFactory();
	private IConnection connection;
	private IModel channel;

	private string exchangeName = "UR3E_AMQP";
	private string ROUTING_KEY_STATE = "robotarm.pt.state";
	private string queue;
	private List<string> messages = new();

	private string hostName = "localhost";
	private string userName = "ur3e";
	private string password = "ur3e";
	private string port = "5672";

	[Signal]
	public delegate void OnMessageEventHandler(string message);

	[Export]
	private AcceptDialog ErrorDialog;


	public override void _Ready()
	{
		if (userName != "")
		{
			factory.UserName = userName;
			GD.Print("Host name set to: " + userName);
		}

		if (hostName != "")
		{
			GD.Print("Host name set to: " + hostName);
		}

		if (password != "")
		{
			factory.Password = password;
			GD.Print("Password set to: " + password);
		}

		if (port != "")
		{
			factory.Port = port.ToInt();
			GD.Print("Port set to: " + port);
		}
		else
		{
			factory.Port = 5672;
			GD.Print("Port not set, using default: 5672");
		}

		try
		{
			connection = factory.CreateConnection();
			channel = connection.CreateModel();
			queue = channel.QueueDeclare(autoDelete: true, exclusive: true);

			channel.QueueBind(queue: queue, exchange: exchangeName, routingKey: ROUTING_KEY_STATE);

			var consumer = new EventingBasicConsumer(channel);
			consumer.Received += (model, ea) =>
			{
				var body = ea.Body.ToArray();
				var message = Encoding.ASCII.GetString(body);
				messages.Add(message);
			};

			GD.Print("Waiting for RabbitMQ messages...");
			channel.BasicConsume(queue: queue, autoAck: true, consumer: consumer);

			if (!connection.IsOpen)
			{
				throw new Exception("RabbitMQ connection is not open!");
			}
			GD.Print("Connection established");
		}
		catch (Exception e)
		{
			GD.PrintErr(e);
			ErrorDialog.Title = "RabbitMQ Error";
			ErrorDialog.DialogText = e.Message;
			ErrorDialog.Show();
		}

	}

	public override void _Process(double delta)
	{
		for (int i = 0; i < messages.Count; i++)
		{
			EmitSignal(SignalName.OnMessage, messages[i]);
		}
		messages.Clear();
	}
}
