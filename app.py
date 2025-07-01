from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
import boto3
from boto3.dynamodb.conditions import Key, Attr
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from decimal import Decimal
import uuid
import random


app = Flask(__name__)
app.secret_key = 'your_secret_key_here' # IMPORTANT: Change this to a strong, random key in production!


# AWS Setup using IAM Role
REGION = 'us-east-1'  # Replace with your actual AWS region
dynamodb = boto3.resource('dynamodb', region_name=REGION)
sns_client = boto3.client('sns', region_name=REGION)


users_table = dynamodb.Table('travelgo_users')
trains_table = dynamodb.Table('trains') # Note: This table is declared but not used in the provided routes.
bookings_table = dynamodb.Table('bookings')


SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:149536455348:TravelGo:75e796e5-dff4-4ae3-a2d8-2de8250743da'  # Replace with actual SNS topic ARN


# Function to send SNS notifications
# This function is duplicated in the original code, removing the duplicate.
def send_sns_notification(subject, message):
    try:
        sns_client.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=subject,
            Message=message
        )
    except Exception as e:
        print(f"SNS Error: Could not send notification - {e}")
        # Optionally, flash an error message to the user or log it more robustly.


# Routes

@app.route('/api/trains_search')
def api_trains_search():
    source = request.args.get('source')
    destination = request.args.get('destination')
    date = request.args.get('date')
    if not source or not destination or not date:
        return jsonify([])
    response = trains_table.scan(
        FilterExpression=Attr('source').eq(source) &
                        Attr('destination').eq(destination) &
                        Attr('date').eq(date)
    )
    matching_trains = response.get('Items', [])
 
    return jsonify(matching_trains)
@app.route('/bus')
def bus():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('bus.html')  # Make sure bus.html exists
@app.route('/api/get_booked_seats', methods=['GET'])
def get_booked_seats():
    bus_id = request.args.get('bus_id')
    travel_date = request.args.get('date')
    
    if not bus_id or not travel_date:
        return jsonify({'success': False, 'message': 'Missing bus_id or date'}), 400

    response = bookings_table.scan(
        FilterExpression=Attr('booking_type').eq('bus') &
                     Attr('item_id').eq(bus_id) &
                     Attr('travel_date').eq(travel_date)
    )
    bookings = response.get('Items', [])


    booked_seats = []
    for b in bookings:
        if 'selected_seats' in b:
            booked_seats.extend(b['selected_seats'])

    return jsonify({'success': True, 'booked_seats': booked_seats})

@app.route('/final_confirm_booking', methods=['POST'])
def final_confirm_booking():
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'User not loggedin'}), 401
    booking_data = session.pop('pending_booking', None)
    if not booking_data:
        return jsonify({'success': False, 'message': 'No pending booking found'}), 400
    try:
        booking_data['booking_date'] = datetime.now().isoformat()
        booking_data['booking_id'] = str(uuid.uuid4())
        bookings_table.put_item(Item=booking_data)
        send_sns_notification("Bus Booking Confirmed", f"Booking by {booking_data['user_email']} on {booking_data['travel_date']}")

        flash('Booking confirmed successfully!', 'success')
        return jsonify({'success': True, 'message': 'Booking confirmed','redirect': url_for('dashboard')})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error:{str(e)}'}), 500
@app.route('/confirm_bus_details')
def confirm_bus_details():
    if 'email' not in session:
        return redirect(url_for('login'))
    name = request.args.get('name')
    source = request.args.get('source')
    destination = request.args.get('destination')
    time = request.args.get('time')
    bus_type = request.args.get('type')
    price_str = request.args.get('price')
    print("DEBUG: Received price =", price_str)
    try:
        price_per_person = Decimal(price_str)
    except (ValueError, TypeError):
        flash('Invalid price format.', 'error')
        return redirect(url_for('bus'))
    travel_date = request.args.get('date')
    num_persons = int(request.args.get('persons'))
    bus_id = request.args.get('busId')
    selected_seats = request.args.getlist('seats[]')  # coming from JS modal
    total_price = price_per_person * Decimal(num_persons)

    booking_details = {
        'name': name,
        'source': source,
        'destination': destination,
        'time': time,
        'type': bus_type,
        'price_per_person': price_per_person,
        'travel_date': travel_date,
        'num_persons': num_persons,
        'total_price': total_price,
        'item_id': bus_id,
        'booking_type': 'bus',
        'user_email': session['email'],
        'selected_seats': selected_seats,

    }
    session['pending_booking'] = booking_details
    return render_template('confirm_bus_details.html',booking=booking_details)
# --- Sample Data Insertion Functions ---
def insert_sample_train_data():
        sample_trains = [
            {"name": "Duronto Express","train_number": "12285", "source": "Hyderabad", "destination": "Delhi","departure_time": "07:00 AM", "arrival_time": "05:00 AM (next day)","price": 1800, "date": "2025-07-10"},
            { "name": "AP Express", "train_number":"12723", "source": "Hyderabad", "destination": "Vijayawada","departure_time": "09:00 AM", "arrival_time": "03:00 PM", "price": 450,"date": "2025-07-10"},
            {"name": "Gouthami Express","train_number": "12737", "source": "Guntur", "destination": "Hyderabad","departure_time": "08:00 PM", "arrival_time": "06:00 AM (next day)","price": 600, "date": "2025-07-10"},
            {"name": "Chennai Express","train_number": "12839", "source": "Bengaluru", "destination":"Chennai", "departure_time": "10:30 AM", "arrival_time": "05:30 PM","price": 750, "date": "2025-07-11"},
            {"name": "Mumbai Mail", "train_number":"12101", "source": "Hyderabad", "destination": "Mumbai","departure_time": "06:00 PM", "arrival_time": "09:00 AM (next day)","price": 1200, "date": "2025-07-10"},
            {"name": "Godavari Express","train_number": "12720", "source": "Vijayawada", "destination":"Hyderabad", "departure_time": "05:00 PM", "arrival_time": "11:00 PM","price": 400, "date": "2025-07-10"},
        ]
        for train in sample_trains:
            train['train_id'] = str(uuid.uuid4())
            trains_table.put_item(Item=train)
@app.route('/')
def index():
    return render_template('index.html')
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        response = users_table.get_item(Key={'email': email})
        if 'Item' in response:
            flash('Email already exists!', 'error')
            return render_template('register.html')

        hashed_password = generate_password_hash(password)
        users_table.put_item(Item={'email': email, 'password': hashed_password})

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        session.pop('username', None)
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        response = users_table.get_item(Key={'email': email})
        user = response.get('Item')

        if user and check_password_hash(user['password'], password):
            session['email'] = email
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password!', 'error')
            return render_template('login.html')
    return render_template('login.html')
@app.route('/logout')
def logout():
    session.pop('email', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))
@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))
    user_email = session['email']
    response = bookings_table.scan(
        FilterExpression=Attr('user_email').eq(user_email)
    )
    user_bookings = response.get('Items', [])
    return render_template('dashboard.html', username=user_email, bookings=user_bookings)
@app.route('/train')
def train():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('train.html')
@app.route('/confirm_train_details')
def confirm_train_details():
    if 'email' not in session:
        return redirect(url_for('login'))
    name = request.args.get('name')
    train_number = request.args.get('trainNumber')
    source = request.args.get('source')
    destination = request.args.get('destination')
    departure_time = request.args.get('departureTime')
    arrival_time = request.args.get('arrivalTime')
    price_str = request.args.get('price')
    print("DEBUG: Received train price =", price_str)
    try:
        price_per_person = Decimal(price_str)
    except (ValueError, TypeError):
        flash('Invalid train price format.', 'error')
        return redirect(url_for('train'))
    travel_date = request.args.get('date')
    num_persons = int(request.args.get('persons'))
    train_id = request.args.get('trainId')
    total_price = price_per_person * Decimal(num_persons)
    booking_details = {
        'name': name,
        'train_number': train_number,
        'source': source,
        'destination': destination,
        'departure_time': departure_time,
        'arrival_time': arrival_time,
        'price_per_person': price_per_person,
        'travel_date': travel_date,
        'num_persons': num_persons,
        'total_price': total_price,
        'item_id': train_id,
        'booking_type': 'train',
        'user_email': session['email']
    }
    session['pending_booking'] = booking_details
    return render_template('confirm_train_details.html', booking=booking_details)
@app.route('/final_confirm_train_booking', methods=['POST'])
def final_confirm_train_booking():
    if 'email' not in session:
        return jsonify({'success': False, 'message': 'User not logged in', 'redirect': url_for('login')}), 401
    booking_data = session.pop('pending_booking', None)
    if not booking_data:
        return jsonify({'success': False, 'message': 'No pending booking to confirm.'}), 400
    try:
        # Fetch already booked seats for this train and date
        response = bookings_table.scan(
                 FilterExpression=Attr('booking_type').eq('train') &
                             Attr('item_id').eq(booking_data['item_id']) &
                             Attr('travel_date').eq(booking_data['travel_date'])
        )
        existing_bookings = response.get('Items', [])

        # after allocating seats:
        booking_data['booking_id'] = str(uuid.uuid4())
        bookings_table.put_item(Item=booking_data)
        send_sns_notification("Train Booking Confirmed", f"Train booking by {booking_data['user_email']} on {booking_data['travel_date']}")

        booked_seats = set()
        for b in existing_bookings:
            if 'seats_display' in b:
                booked_seats.update(b['seats_display'].split(', '))
        # Generate available seat numbers (e.g., S1 to S100)
        all_seats = [f"S{i}" for i in range(1, 101)]
        available_seats = [seat for seat in all_seats if seat not in booked_seats]
        if len(available_seats) < booking_data['num_persons']:
            return jsonify({'success': False, 'message': 'Not enough seats available'}), 400
        # Assign seat
        allocated_seats = available_seats[:booking_data['num_persons']]
        booking_data['seats_display'] = ', '.join(allocated_seats)
        booking_data['booking_date'] = datetime.now().isoformat()
        flash('Train booking confirmed successfully!', 'success')
        return jsonify({
            'success': True,
            'message': 'Train booking confirmed successfully!',
            'redirect': url_for('dashboard')
        })
    except Exception as e:
        flash(f'Failed to confirm train booking: {str(e)}', 'error')
        return jsonify({'success': False, 'message': f'Failed to confirm train booking: {str(e)}'}), 500
@app.route('/cancel_booking', methods=['POST'])
def cancel_booking():
    if 'email' not in session:
        return redirect(url_for('login'))
    booking_id = request.form.get('booking_id')
    user_email = session['email']
    if not booking_id:
        flash("Error: Booking ID is missing for cancellation.", 'error')
        return redirect(url_for('dashboard'))
    try:
        response = bookings_table.get_item(Key={'booking_id': booking_id, 'user_email': session['email']})
        if 'Item' in response:
            bookings_table.delete_item(Key={'booking_id': booking_id, 'user_email': session['email']})
            flash("Cancelled successfully", 'success')
        else:
            flash("Booking not found or unauthorized.", 'error')

        response = bookings_table.get_item(Key={'booking_id': booking_id, 'user_email': session['email']})
        if 'Item' in response:
            bookings_table.delete_item(Key={'booking_id': booking_id, 'user_email': session['email']})
            flash("Cancelled successfully", 'success')
        else:
            flash("Booking not found or unauthorized.", 'error')

    except Exception as e:
        flash(f"Failed to cancel booking: {str(e)}", 'error')
    return redirect(url_for('dashboard'))
@app.route('/hotel')
def hotel():
    return render_template('hotel.html')
@app.route('/confirm_hotel_details')
def confirm_hotel_details():
    booking = {
        'name':            request.args.get('name'),
        'location':        request.args.get('location'),
        'checkin_date':    request.args.get('checkin'),
        'checkout_date':   request.args.get('checkout'),
        'num_rooms':       int(request.args.get('rooms')),
        'num_guests':      int(request.args.get('guests')),
        price_str = request.args.get('price')
        print("DEBUG: Hotel price =", price_str)
        try:
            price_per_night = Decimal(price_str)
        except (ValueError, TypeError):
            flash("Invalid hotel price format.", 'error')
            return redirect(url_for('hotel'))
        'rating':          int(request.args.get('rating'))
    }
    # compute nights & total
    ci = datetime.fromisoformat(booking['checkin_date'])
    co = datetime.fromisoformat(booking['checkout_date'])
    nights = (co - ci).days
    booking['total_price'] = booking['price_per_night'] * booking['num_rooms'] * nights
    booking['nights'] = nights
    return render_template('confirm_hotel_details.html', booking=booking)
# Consume the form POST, save to Mongo, then redirect
@app.route('/confirm_hotel_booking', methods=['POST'])
def confirm_hotel_booking():
    if 'email' not in session:
        return redirect(url_for('login'))
    # pull values from the hidden inputs
    booking = {
        'booking_type':    'hotel',
        'name':            request.form['hotel_name'],
        'location':        request.form['location'],
        'checkin_date':    request.form['checkin'],
        'checkout_date':   request.form['checkout'],
        'num_rooms':       int(request.form['rooms']),
        'num_guests':      int(request.form['guests']),
        'price_per_night': price_per_night,
        'rating':          int(request.form['rating']),
        'user_email':      session['email'],
        'booking_date':    datetime.now().isoformat()
    }
    # recompute total for safety
    ci = datetime.fromisoformat(booking['checkin_date'])
    co = datetime.fromisoformat(booking['checkout_date'])
    nights = (co - ci).days
    booking['total_price'] = booking['price_per_night'] * booking['num_rooms'] * nights
    booking['booking_id'] = str(uuid.uuid4())
    bookings_table.put_item(Item=booking)
    send_sns_notification("Hotel Booking Confirmed", f"Hotel booking by {booking['user_email']} from {booking['checkin_date']} to {booking['checkout_date']}")

    flash('Hotel booking confirmed successfully!', 'success')
    return redirect(url_for('dashboard'))
@app.route('/flight')
def flight():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('flight.html')
@app.route('/flight_seat_selection')
def flight_seat_selection():
    flight_id = request.args.get('flight_id')
    # Fetch booked seats from database for this flight_id
    booked = bookings_table.find({"flight_id": flight_id})
    booked_seats = []
    for b in booked:
        if 'selected_seats' in b:
            booked_seats.extend(b['selected_seats'])

    return render_template('flight_seat_selection.html',
        flight_id=flight_id,
        airline=request.args.get('airline'),
        flight_number=request.args.get('flight_number'),
        source=request.args.get('source'),
        destination=request.args.get('destination'),
        departure_time=request.args.get('departure'),
        arrival_time=request.args.get('arrival'),
        travel_date=request.args.get('date'),
        num_persons=request.args.get('passengers'),
        price_per_person=request.args.get('price'),
        flight_class=request.args.get('class'),
        booked_seats=booked_seats
    )

# Show confirmation page
@app.route('/confirm_flight_details')
def confirm_flight_details():
    flight_id = request.args.get('flight_id')
    airline = request.args.get('airline')
    flight_number = request.args.get('flight_number')
    source = request.args.get('source')
    destination = request.args.get('destination')
    departure_time = request.args.get('departure')
    arrival_time = request.args.get('arrival')
    travel_date = request.args.get('date')
    num_persons = int(request.args.get('passengers'))
    price_str = request.args.get('price')
    print("DEBUG: Flight price =", price_str)
    try:
        price_per_person = Decimal(price_str)
    except (ValueError, TypeError):
        flash("Invalid flight price format.", 'error')
        return redirect(url_for('flight'))
    flight_class = request.args.get('class')  # ✅ make sure this is fetched

    total_price = Decimal(num_persons) * price_per_person

    booking = {
        'flight_id': flight_id,
        'airline': airline,
        'flight_number': flight_number,
        'source': source,
        'destination': destination,
        'departure_time': departure_time,
        'arrival_time': arrival_time,
        'travel_date': travel_date,
        'num_persons': num_persons,
        'price_per_person': price_per_person,
        'total_price': total_price,
        'flight_class': flight_class  # ✅ pass this to template
    }

    return render_template('confirm_flight_details.html', booking=booking)
# Handle final booking
@app.route('/confirm_flight_booking', methods=['POST'])
def confirm_flight_booking():
    if 'email' not in session:
        return redirect(url_for('login'))

    selected_seats_str = request.form.get('selected_seats')
    selected_seats = selected_seats_str.split(",") if selected_seats_str else []

    flight_id = request.form['flight_id']
    travel_date = request.form['travel_date']
    flight_class = request.form['flight_class']

    # Restrict seats only within same flight, date and class
    response = bookings_table.scan(
        FilterExpression=Attr('flight_id').eq(flight_id) &
                         Attr('travel_date').eq(travel_date) &
                         Attr('booking_type').eq('flight') &
                         Attr('flight_class').eq(flight_class)
    )
    existing_bookings = response.get('Items', [])

    booking['booking_id'] = str(uuid.uuid4())
    bookings_table.put_item(Item=booking)
    send_sns_notification("Flight Booking Confirmed", f"Flight booking by {booking['user_email']} on {booking['travel_date']} in {flight_class}")

    already_booked = set()
    for b in existing_bookings:
        if 'selected_seats' in b:
            already_booked.update(b['selected_seats'])

    for seat in selected_seats:
        if seat in already_booked:
            flash(f"Seat {seat} is already booked in {flight_class}. Please re-select.", 'error')
            return redirect(url_for('flight_seat_selection', **request.form))

    booking = {
        'booking_type':      'flight',
        'flight_id':         flight_id,
        'airline':           request.form['airline'],
        'flight_number':     request.form['flight_number'],
        'source':            request.form['source'],
        'destination':       request.form['destination'],
        'departure_time':    request.form['departure_time'],
        'arrival_time':      request.form['arrival_time'],
        'flight_class':      flight_class,  # ✅ important to store this
        'travel_date':       travel_date,
        'num_persons':       Decimal(request.form['num_persons']),
        'price_per_person':  Decimal(request.form['price_per_person']),
        'total_price':       Decimal(request.form['total_price']),
        'selected_seats':    selected_seats,
        'user_email':        session['email'],
        'booking_date':      datetime.now().isoformat()
    }

    flash('Flight booking confirmed successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/faqs')
def faqs():
    return render_template('faqs.html')
@app.route('/booked_seats')
def booked_seats():
    bus_id = request.args.get('bus_id')
    date = request.args.get('date')

    if not bus_id or not date:
        return jsonify([])

    response = bookings_table.scan(
        FilterExpression=Attr('item_id').eq(bus_id) &
                         Attr('travel_date').eq(date) &
                         Attr('booking_type').eq('bus')
    )

    bookings = response.get('Items', [])
    booked_seats = []
    for b in bookings:
        if "selected_seats" in b:
            booked_seats.extend(b["selected_seats"])

    return jsonify([str(seat) for seat in booked_seats])


def get_flight_booked_seats(flight_id, travel_date):
    booked = bookings_table.find({
        'booking_type': 'flight',
        'flight_id': flight_id,
        'travel_date': travel_date
    })
    booked_seats = []
    for b in booked:
        if 'selected_seats' in b:
            booked_seats.extend(b['selected_seats'])
    return booked_seats
@app.route('/get_booked_seats')
def get_flight_booked_seats():
    flight_id = request.args.get('flight_id')
    travel_date = request.args.get('travel_date')
    flight_class = request.args.get('flight_class')

    if not flight_id or not travel_date or not flight_class:
        return jsonify({'booked_seats': []})

    response = bookings_table.scan(
        FilterExpression=Attr('flight_id').eq(flight_id) &
                         Attr('travel_date').eq(travel_date) &
                         Attr('flight_class').eq(flight_class) &
                         Attr('booking_type').eq('flight')
    )
    bookings = response.get('Items', [])
    
    booked_seats = []
    for b in bookings:
        if "selected_seats" in b:
            booked_seats.extend(b["selected_seats"])

    return jsonify({'booked_seats': booked_seats})




if __name__ == '__main__':
    # IMPORTANT: In a production environment, disable debug mode and specify a production-ready host.
    app.run(debug=True, host='0.0.0.0')
