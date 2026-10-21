from flask import Flask,render_template,redirect,request
from api.v1 import model,dataset

m = model()
m.fit()
d = dataset()
d.update()
teams = d.show_teams()

app = Flask(__name__)

@app.route('/')
def toHome():
    return redirect('/home')

@app.route('/home')
def home():
    return render_template('home.html')

@app.route('/predict')
def predict():
    return render_template('predict.html', teams=teams, predicted=False)

@app.route('/predict/complete', methods=['POST'])
def predictRes():
    res = m.predict_match(request.form.get('team-1'),request.form.get('team-2'))
    return render_template('predict.html', res=res, predicted=True)

if __name__ == '__main__':
    app.run(debug=True)